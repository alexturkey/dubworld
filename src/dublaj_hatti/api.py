"""Stable Python API: every pipeline stage on its own, file in -> file out.

    from dublaj_hatti import api

    video = api.indir("https://...", "work/")                    # optional: extras youtube / galeri
    sesler = api.ayir("talk.mp4", "work/")                        # {"vokal": ..., "arka_plan": ...} (extras separation)
    tr = api.yaziya_dok("talk.mp4", "work/transcript.json")      # speech-to-text + word timing
    tr = api.hizala("talk.wav", "my_text.json", "work/aligned.json", dil="en")   # word timing for a known text
    tr_tr = api.cevir("work/transcript.json", "work/translation.json", hedef_dil="tr")
    api.seslendir("Merhaba dünya.", "work/tts/")                  # plain text -> speech (WAV)
    api.seslendir("work/translation.json", "work/tts/")           # timed segments -> timed track + speech.json
    api.altyazi("work/transcript.json", "work/sub.ass", kip="karaoke")
    api.birlestir("talk.mp4", "out.mp4", ses="work/tts/speech.wav", altyazi="work/sub.srt")
    api.dubla("talk.mp4")                                         # the whole recommended flow

Contract (semantic versioning applies to everything in ``__all__``):
  * inputs are paths (``str`` or ``Path``) or plain text; outputs are written to the given path and the path is returned
  * stage files follow ``dublaj_hatti.bicimler`` (JSON Schemas in ``dublaj_hatti/semalar/``)
  * ``ayarlar`` takes the same ``"section.key": value`` pairs as ``--ayar`` / ``varsayilan.toml``
  * heavy libraries (torch, models) load only inside the stage that needs them; importing this module is cheap
  * errors: ``AyarHatasi`` (wrong setting, exit code 2 in the CLI), ``KaynakHatasi`` (bad source),
    ``BicimHatasi`` (stage file does not match its schema), ``AsamaHatasi`` (the stage itself failed),
    ``LisansOnayiGerekli`` (a non-commercial / conditional engine such as Supertonic was not accepted yet)
  * license gate: every stage that runs an engine passes the same gate as the CLI, GUI and web
    (``dublaj_hatti.lisans_onayi.kapi_adlar``) before any work; accept once with ``lisans_onay=True``
    or ``DUBLAJ_LISANS_ONAY=1`` (stored in ayarlar/lisans_onaylari.json, PRIVACY.md)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from dublaj_hatti.bicimler import (
    SEMA_CEVIRI,
    SEMA_SESLENDIRME,
    BicimHatasi,
    altyazi_yaz,
    dogrula,
    json_yaz,
    transkript_oku,
    transkript_olustur,
)
from dublaj_hatti.kaynak_girdisi import KaynakHatasi, baglanti_turu, kaynak_dogrula
from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, kapi_adlar, secili_motorlar
from dublaj_hatti.yapilandirma import AyarHatasi, ayarlari_yukle

__all__ = [
    "AsamaHatasi",
    "AyarHatasi",
    "BicimHatasi",
    "KaynakHatasi",
    "LisansOnayiGerekli",
    "ASAMALAR",
    "ayarlarla",
    "indir",
    "ses_cikar",
    "ayir",
    "yaziya_dok",
    "hizala",
    "cevir",
    "seslendir",
    "altyazi",
    "birlestir",
    "dubla",
]

logger = logging.getLogger("dublaj_hatti.api")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
CUMLE_SONU = re.compile(r"(?<=[.!?…])\s+")
PARCA_ARASI_SN = 0.25

# stage name -> (CLI subcommand, extras that must be installed, input, output); docs/mimari.md draws the same table
ASAMALAR: dict[str, dict[str, str]] = {
    "indir": {"komut": "indir", "ek": "youtube | galeri", "girdi": "https link", "cikti": "video file"},
    "ses_cikar": {"komut": "ses-cikar", "ek": "-", "girdi": "video", "cikti": "WAV"},
    "ayir": {"komut": "ayir", "ek": "separation", "girdi": "video / audio", "cikti": "vocals.wav + background.wav"},
    "yaziya_dok": {"komut": "yaziya-dok", "ek": "stt", "girdi": "video / audio", "cikti": "transcript.json (+ .srt)"},
    "hizala": {"komut": "hizala", "ek": "hizalama", "girdi": "audio + transcript.json", "cikti": "transcript.json"},
    "cevir": {"komut": "cevir", "ek": "ceviri", "girdi": "transcript.json", "cikti": "translation.json"},
    "seslendir": {"komut": "seslendir", "ek": "tts", "girdi": "text / .txt / translation.json",
                  "cikti": "WAV (+ speech.json)"},
    "altyazi": {"komut": "altyazi", "ek": "-", "girdi": "transcript.json / translation.json",
                "cikti": "SRT / VTT / ASS"},
    "birlestir": {"komut": "birlestir", "ek": "-", "girdi": "video + audio and/or subtitle", "cikti": "MP4"},
    "dubla": {"komut": "dubla", "ek": "onerilen", "girdi": "video / link", "cikti": "dubbed MP4 + files"},
}


class AsamaHatasi(RuntimeError):
    """A stage could not finish (missing model, engine error, ffmpeg failure)."""


# Stages that run no engine from the registry (kayit): ffmpeg, subtitle writer, CTC alignment (MIT / CC-BY-4.0).
# Every other stage calls _lisans() first (tests/test_lisans_kapisi_girisler.py checks both lists).
MOTORSUZ_ASAMALAR = frozenset({"ses_cikar", "hizala", "altyazi", "birlestir"})


def _lisans(adlar: list[str], onay: bool) -> None:
    """The one license gate (lisans_onayi.kapi_adlar): raises LisansOnayiGerekli before any work is done."""
    kapi_adlar(adlar, onay)


# --- shared helpers --------------------------------------------------------------------------------------
_KATMAN: ContextVar[tuple[str | None, tuple[str, ...]]] = ContextVar("dublaj_hatti_api_katman", default=(None, ()))


@contextmanager
def ayarlarla(dosya: str | Path | None = None, ifadeler: list[str] | None = None) -> Iterator[None]:
    """Settings layer for the stage calls inside the block (same as ``--ayarlar`` / ``--ayar`` of the CLI)."""
    jeton = _KATMAN.set((str(dosya) if dosya else None, tuple(ifadeler or ())))
    try:
        yield
    finally:
        _KATMAN.reset(jeton)


def _ayar(ayarlar: dict[str, Any] | None, **asama: Any) -> dict[str, Any]:
    """Validated settings. Order: varsayilan.toml < user files < :func:`ayarlarla` layer < explicit stage arguments
    (``None`` = not given) < ``ayarlar`` dict of the caller."""
    dosya, katman = _KATMAN.get()
    ifadeler = list(katman)
    ifadeler += [f"{k.replace('__', '.')}={_metin(v)}" for k, v in asama.items() if v is not None]
    ifadeler += [f"{k}={_metin(v)}" for k, v in (ayarlar or {}).items()]
    return ayarlari_yukle(dosya, ifadeler)


def _metin(deger: Any) -> str:
    if isinstance(deger, bool):
        return "true" if deger else "false"
    return str(deger)


def _hazirla(ayar: dict[str, Any]) -> None:
    """Environment before torch is imported (offline model cache, local ffmpeg, CPU choice)."""
    from dublaj_hatti.cli import ortami_hazirla

    ortami_hazirla(ayar["genel.cihaz"])


def _cfg(ayar: dict[str, Any]) -> Any:
    from dublaj_hatti.yapilandirma import dubconfig_olustur

    cfg, _cozum = dubconfig_olustur(ayar)
    return cfg


@contextmanager
def _calisma_klasoru(ust: Path, ad: str) -> Iterator[Path]:
    """Scratch folder next to the output; removed when the stage succeeds, kept for diagnosis when it fails."""
    ust.mkdir(parents=True, exist_ok=True)
    klasor = Path(tempfile.mkdtemp(prefix=f".{ad}_", dir=ust))
    yield klasor
    shutil.rmtree(klasor, ignore_errors=True)


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise AsamaHatasi("ffmpeg bulunamadı: scripts/kur.ps1 -Adim modeller (FFmpeg bu adımla iner) ya da ffmpeg'i PATH'e ekleyin")
    return yol


def _calistir(komut: list[str]) -> None:
    sonuc = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=NO_WINDOW)
    if sonuc.returncode != 0:
        son = (sonuc.stderr or "").strip().splitlines()[-1:] or ["?"]
        raise AsamaHatasi(f"{Path(komut[0]).name} hata verdi (kod {sonuc.returncode}): {son[0]}")


def _ses_dosyasi_mi(yol: Path) -> bool:
    return yol.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus"}


# --- stages ----------------------------------------------------------------------------------------------
def indir(url: str, hedef_klasor: str | Path, lisans_onay: bool = False) -> Path:
    """Downloads one video from an https link (yt-dlp or gallery-dl, optional extras). Returns the video path.

    Only content you own or are allowed to use; the site's terms are your responsibility.
    """
    url = kaynak_dogrula(url)
    if not url.lower().startswith(("https://", "www.")):
        raise KaynakHatasi("indir yalnız bağlantı alır; yerel dosya zaten hazır")
    _lisans(["gallery_dl" if baglanti_turu(url) == "galeri" else "yt_dlp"], lisans_onay)
    hedef = Path(hedef_klasor)
    hedef.mkdir(parents=True, exist_ok=True)
    if baglanti_turu(url) == "galeri":
        from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.galeri_indirici import indir as galeri_indir

        return Path(galeri_indir(url, hedef, logger=logger))
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_20_kaynak_alma.youtube_downloader import download_video

    sonuc = download_video(url=url, download_dir=hedef, logger=logger)
    return Path(sonuc["video_path"])


def ses_cikar(medya: str | Path, hedef: str | Path, ornekleme: int = 16000, kanal: int = 1) -> Path:
    """Extracts the audio track as WAV (ffmpeg). 16 kHz mono is what speech-to-text expects."""
    medya, hedef = Path(medya), Path(hedef)
    if not medya.is_file():
        raise KaynakHatasi(f"dosya bulunamadı: {medya}")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.stem + ".part.wav")
    _calistir([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(medya), "-vn",
               "-ac", str(kanal), "-ar", str(ornekleme), "-c:a", "pcm_s16le", str(gecici)])
    os.replace(gecici, hedef)
    return hedef


def ayir(medya: str | Path, hedef_klasor: str | Path, cihaz: str | None = None,
         lisans_onay: bool = False) -> dict[str, Path]:
    """Separates speech from background with Demucs (htdemucs). Returns {"vokal": WAV, "arka_plan": WAV}."""
    import importlib.util

    _lisans(["demucs"], lisans_onay)
    if importlib.util.find_spec("demucs") is None:
        raise AyarHatasi("ses ayrıştırma Demucs ister ve kurulu değil: pip install .[separation]")
    ayar = _ayar(None, genel__cihaz=cihaz)
    _hazirla(ayar)
    from dublaj_hatti.bolum_10_kaynak_edinme.adim_50_asr_sesi_hazirlama.demucs_cleaner import clean_audio_with_demucs

    hedef = Path(hedef_klasor)
    with _calisma_klasoru(hedef, "ayir") as is_klasoru:
        kaynak = ses_cikar(medya, is_klasoru / "demucs_source.wav", ornekleme=44100, kanal=2)
        vokal = Path(clean_audio_with_demucs(str(kaynak), str(is_klasoru), prefer_device=ayar["genel.cihaz"],
                                             logger=logger, prepare_asr_ready=False))
        arka = vokal.with_name("no_vocals.wav")
        if not vokal.is_file() or not arka.is_file():
            raise AsamaHatasi("Demucs çıktısı eksik (vocals.wav / no_vocals.wav)")
        sonuc = {"vokal": hedef / "vocals.wav", "arka_plan": hedef / "background.wav"}
        os.replace(vokal, sonuc["vokal"])
        os.replace(arka, sonuc["arka_plan"])
    return sonuc


def yaziya_dok(medya: str | Path, hedef: str | Path, motor: str | None = None, dil: str | None = None,
               cihaz: str | None = None, srt: bool = True, ayarlar: dict[str, Any] | None = None,
               lisans_onay: bool = False) -> Path:
    """Speech-to-text with word timestamps (CTC alignment included) -> transcript.json (+ .srt next to it).

    ``motor``: any engine of ``dubla kontrol`` (faster-whisper, whisperx, crisperwhisper_turbo_ct2, ...);
    None = the recommended choice for this machine. ``dil``: source language code or "auto" (default: transkripsiyon.kaynak_dil).
    ``cihaz``: auto / cuda / cpu (default: genel.cihaz).
    """
    ayar = _ayar(ayarlar, genel__is_turu="transkript", genel__cihaz=cihaz, transkripsiyon__motor=motor,
                 transkripsiyon__kaynak_dil=dil)
    _lisans(secili_motorlar(ayar), lisans_onay)  # "auto": an installed non-commercial STT is asked for too
    _hazirla(ayar)
    cfg = _cfg(ayar)
    from dublaj_hatti.bolum_00_omurga.core.dubber import transcribe_and_align

    medya, hedef = Path(medya), Path(hedef)
    with _calisma_klasoru(hedef.parent, "yaziya_dok") as is_klasoru:
        wav = medya if medya.suffix.lower() == ".wav" else ses_cikar(medya, is_klasoru / "source_audio.wav")
        segmentler, tespit_dili, _hizalama = transcribe_and_align(str(wav), cfg, str(is_klasoru))
    veri = transkript_olustur(segmentler, tespit_dili, motor=cfg.transcription_engine, kaynak=str(medya))
    json_yaz(hedef, dogrula(veri))
    if srt:
        altyazi_yaz(veri, hedef.with_suffix(".srt"))
    return hedef


def hizala(ses: str | Path, transkript: str | Path, hedef: str | Path, dil: str | None = None,
           cihaz: str | None = None) -> Path:
    """Word timing for a known text (wav2vec2 CTC forced alignment) -> transcript.json with ``words``.

    ``transkript``: transcript.json / WhisperX JSON with segment times, or a .txt file (one block = whole audio).
    """
    ayar = _ayar(None, genel__cihaz=cihaz)
    _hazirla(ayar)
    from dublaj_hatti.bolum_00_omurga.runtime.donanim import cihaz_coz
    from dublaj_hatti.bolum_30_hizalama_ve_segment.ctc_kelime_hizalama.client import run_ctc_word_alignment

    ses, transkript, hedef = Path(ses), Path(transkript), Path(hedef)
    with _calisma_klasoru(hedef.parent, "hizala") as is_klasoru:
        wav = ses if ses.suffix.lower() == ".wav" else ses_cikar(ses, is_klasoru / "audio.wav")
        if transkript.suffix.lower() == ".txt":
            metin = " ".join(transkript.read_text(encoding="utf-8-sig").split())
            sure = _wav_suresi(wav)
            girdi = transkript_olustur([{"start": 0.0, "end": sure, "text": metin}], dil or "und")
        else:
            girdi = transkript_oku(transkript, dil)
        dil = dil or girdi["language"]
        if dil in ("", "und", "auto"):
            raise AyarHatasi("hizalama dili bilinmiyor: dil='en' gibi verin")
        segmentler = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in girdi["segments"]]
        istek = is_klasoru / "segments.json"
        istek.write_text(json.dumps(segmentler, ensure_ascii=False), encoding="utf-8")
        sonuc = run_ctc_word_alignment(wav, istek, dil, ayar["genel.onbellek_klasoru"] or _onbellek(),
                                       timeout_seconds=3600, device=cihaz_coz(ayar["genel.cihaz"]))
    hizali = sonuc.get("segments") or []
    if len(hizali) == len(girdi["segments"]):  # the aligner may split at sentence ends; keep speakers only 1:1
        for kaynak_seg, yeni in zip(girdi["segments"], hizali, strict=True):
            if "speaker" in kaynak_seg:
                yeni["speaker"] = kaynak_seg["speaker"]
    veri = transkript_olustur(hizali, dil, motor="ctc_kelime_hizalama", kaynak=girdi.get("source"))
    return json_yaz(hedef, dogrula(veri))


def _onbellek() -> str:
    from dublaj_hatti.bolum_00_omurga.runtime.asset_paths import huggingface_home

    return str(huggingface_home())


def _wav_suresi(wav: Path) -> float:
    import wave

    with wave.open(str(wav), "rb") as dosya:
        return dosya.getnframes() / float(dosya.getframerate())


def cevir(transkript: str | Path, hedef: str | Path, hedef_dil: str = "tr", arka_uc: str = "yerel",
          kaynak_dil: str | None = None, cihaz: str | None = None, lisans_onay: bool = False) -> Path:
    """Translates every segment, keeping the timing -> translation.json (``source_text`` keeps the original).

    ``arka_uc``: yerel (Opus-MT, offline, English -> Turkish), codex, claude_code, gemini_2_5_flash, ... or auto.
    """
    girdi = transkript_oku(transkript, kaynak_dil)
    kaynak_dil = kaynak_dil or girdi["language"]
    ayar = _ayar(None, genel__is_turu="dublaj", genel__cihaz=cihaz, genel__hedef_dil=hedef_dil,
                 ceviri__arka_uc=arka_uc)
    _lisans([ayar["ceviri.arka_uc"]], lisans_onay)
    _hazirla(ayar)
    cfg = _cfg(ayar)
    from dublaj_hatti.bolum_00_omurga.core.dubber import _create_segment_translator
    from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import NihaiDublajSegmenti

    segmentler = [NihaiDublajSegmenti(index=i, start=s["start"], end=s["end"], text=s["text"],
                                      speaker=s.get("speaker", ""), words=s.get("words"))
                  for i, s in enumerate(girdi["segments"], 1)]
    hedef = Path(hedef)
    with _calisma_klasoru(hedef.parent, "cevir") as is_klasoru:
        cevirmen = _create_segment_translator(cfg, {}, kaynak_dil)
        # Konumsal: yerel çevirmen ikinci parametreye run_dir, LLM köprüsü output_dir der (dubber de böyle çağırır).
        metinler = cevirmen.translate_segments(segmentler, str(is_klasoru))
    if len(metinler) != len(segmentler):
        raise AsamaHatasi(f"çeviri {len(segmentler)} segment yerine {len(metinler)} döndürdü")
    cikti = [{"start": s["start"], "end": s["end"], "text": str(m).strip(), "source_text": s["text"],
              **({"speaker": s["speaker"]} if s.get("speaker") else {})}
             for s, m in zip(girdi["segments"], metinler, strict=True)]
    veri = transkript_olustur(cikti, hedef_dil, sema=SEMA_CEVIRI, kaynak_dil=kaynak_dil,
                              motor=cfg.llm_backend or cfg.translator_engine, kaynak=girdi.get("source"))
    return json_yaz(hedef, dogrula(veri))


def seslendir(girdi: str | Path, hedef_klasor: str | Path, motor: str = "supertonic", ses: str | None = None,
              dil: str = "tr", ayarlar: dict[str, Any] | None = None, lisans_onay: bool = False) -> Path:
    """Text to speech.

    * ``girdi`` is text or a .txt file -> one WAV (``speech.wav``); sentences are read in order.
    * ``girdi`` is a transcript/translation JSON -> segments are spoken at their times: ``speech.wav`` (timed track)
      + ``speech.json`` (schema speech@1, one WAV per segment). Returns speech.json.

    ``motor``: supertonic (CPU or GPU, default) or voxcpm2 (NVIDIA GPU, separate install).
    ``ses``: Supertonic F1-F5 / M1-M5, VoxCPM2 voice folder such as hazir/haber_spikeri.
    """
    hedef = Path(hedef_klasor)
    hedef.mkdir(parents=True, exist_ok=True)
    yol = Path(str(girdi)) if len(str(girdi)) < 1024 and "\n" not in str(girdi) else None
    json_girdi = yol is not None and yol.suffix.lower() == ".json" and yol.is_file()
    ses_anahtari = "ses.voxcpm2_ses" if motor == "voxcpm2" else "ses.supertonic_ses"
    ek = dict(ayarlar or {})
    if ses:
        ek[ses_anahtari] = ses
    # is_turu=transkript: no translation backend is resolved for a speech-only call
    ayar = _ayar(ek, genel__is_turu="transkript", genel__hedef_dil=dil, ses__motor=motor,
                 ses__konusmaci_cinsiyetine_gore_ses=False)
    _lisans([ayar["ses.motor"]], lisans_onay)  # Supertonic (OpenRAIL-M): same gate as `dubla <video>`
    _hazirla(ayar)
    if not json_girdi:
        metin = yol.read_text(encoding="utf-8-sig") if yol is not None and yol.suffix.lower() == ".txt" \
            and yol.is_file() else str(girdi)
        if not metin.strip():
            raise KaynakHatasi("seslendirilecek metin boş")
        return _metni_seslendir(metin, hedef, ayar)
    assert yol is not None  # json_girdi implies a path
    veri = transkript_oku(yol)
    cfg = _cfg(ayar)
    import soundfile as sf

    from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import NihaiDublajSegmenti
    from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.service import build_dubbed_audio

    segmentler = [NihaiDublajSegmenti(index=i, start=s["start"], end=s["end"], text=s["text"],
                                      speaker=s.get("speaker", ""))
                  for i, s in enumerate(veri["segments"], 1) if s["text"].strip()]
    from dublaj_hatti.bolum_00_omurga.core.dubber import (
        _apply_engine_sample_rate,
        _apply_supertonic_manual_voice_metadata_if_needed,
    )

    _apply_engine_sample_rate(cfg, logger)
    with _calisma_klasoru(hedef, "seslendir") as is_klasoru:
        # same voice routing as the full flow's "ses_yonlendirme" stage (one voice for every segment here)
        _apply_supertonic_manual_voice_metadata_if_needed(segmentler, cfg)
        if cfg.tts_engine == "supertonic":
            from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.speed_policy import apply_supertonic_voice_speed_plan

            apply_supertonic_voice_speed_plan(segmentler, str(is_klasoru), default_voice_id=cfg.tts_voice_id or "F1")
        sonuc = build_dubbed_audio(segmentler, cfg, str(is_klasoru))
    (hedef / "parcalar").mkdir(exist_ok=True)
    kayitlar = []
    for seg in segmentler:
        dalga = sonuc.segment_audios.get(seg.index)
        if dalga is None:
            continue
        parca = Path("parcalar") / f"{seg.index:05d}.wav"
        sf.write(hedef / parca, dalga, cfg.sample_rate)
        kayitlar.append({"id": seg.index, "start": seg.start, "end": seg.end, "text": seg.text,
                         "audio": parca.as_posix(), "duration": round(len(dalga) / cfg.sample_rate, 3)})
    sf.write(hedef / "speech.wav", sonuc.audio, cfg.sample_rate)
    manifest = {"schema": SEMA_SESLENDIRME, "engine": motor, "voice": ayar[ses_anahtari], "language": dil,
                "sample_rate": int(cfg.sample_rate), "audio": "speech.wav", "segments": kayitlar}
    return json_yaz(hedef / "speech.json", dogrula(manifest))


def _metni_seslendir(metin: str, hedef: Path, ayar: dict[str, Any]) -> Path:
    if ayar["ses.motor"] == "supertonic":
        from dublaj_hatti.bolum_50_seslendirme.metinden_seslendirme import synthesize_text_to_speech

        with _calisma_klasoru(hedef, "seslendir") as is_klasoru:
            sonuc = synthesize_text_to_speech(metin, is_klasoru, ayar["ses.supertonic_ses"],
                                              language=ayar["genel.hedef_dil"], base_name="speech")
            os.replace(sonuc.original_wav_path, hedef / "speech.wav")
        return hedef / "speech.wav"
    if ayar["ses.motor"] == "voxcpm2":
        import numpy as np
        import soundfile as sf

        from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts.api import VoxCPM2Hatasi, _run_engine

        cumleler = [c.strip() for c in CUMLE_SONU.split(" ".join(metin.split())) if c.strip()]
        parcalar = [{"index": i, "text": c} for i, c in enumerate(cumleler, 1)]
        with _calisma_klasoru(hedef, "seslendir") as is_klasoru:
            ozet = _run_engine(ayar["ses.voxcpm2_ses"], parcalar, _cfg(ayar), is_klasoru)
            if ozet.get("hatali"):
                raise VoxCPM2Hatasi(f"VoxCPM2 şu cümleleri bitiremedi: {ozet['hatali'][:10]}")
            dalgalar, oran = [], 0
            for p in parcalar:
                dalga, oran = sf.read(ozet["wavlar"][str(p["index"])], dtype="float32")
                dalgalar += [dalga, np.zeros(int(oran * PARCA_ARASI_SN), dtype="float32")]
            sf.write(hedef / "speech.wav", np.concatenate(dalgalar[:-1]), oran)
        return hedef / "speech.wav"
    raise AyarHatasi(f"metinden ses bu motoru desteklemiyor: {ayar['ses.motor']} (supertonic, voxcpm2)")


def altyazi(transkript: str | Path, hedef: str | Path, bicim: str | None = None, kip: str = "segment") -> Path:
    """Subtitle file from transcript.json / translation.json / WhisperX JSON (no model, no GPU).

    ``bicim``: srt, vtt, ass (default: from the file extension). ``kip``: segment, kelime (one word per cue),
    karaoke (word highlighting; ASS ``\\k`` tags or WebVTT timestamps; needs word times).
    """
    return altyazi_yaz(transkript_oku(transkript), hedef, bicim, kip)


def birlestir(video: str | Path, hedef: str | Path, ses: str | Path | None = None, altyazi: str | Path | None = None,
              yak: bool = False, arka_plan: str | Path | None = None, arka_plan_db: float = -8.0,
              ai_etiketi: bool = True) -> Path:
    """Puts the video together with a new audio track and/or subtitles (ffmpeg).

    * ``ses``: replaces the audio (video stream copied, no re-encode)
    * ``arka_plan``: mixed under ``ses`` at ``arka_plan_db`` (e.g. background.wav from :func:`ayir`)
    * ``altyazi``: soft subtitle track (mov_text) or, with ``yak=True``, burned into the picture (re-encode)
    * ``ai_etiketi``: writes the "AI-dubbed" metadata tag when a new audio track is used
    """
    video, hedef = Path(video), Path(hedef)
    if not video.is_file():
        raise KaynakHatasi(f"video bulunamadı: {video}")
    if ses is None and altyazi is None:
        raise AyarHatasi("birlestir için ses ya da altyazı verin")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(hedef.stem + ".part" + hedef.suffix)
    komut = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(video)]
    girdiler = 1
    ses_eslemesi = ["-map", "0:a?"]
    if ses is not None:
        komut += ["-i", str(ses)]
        ses_no, girdiler = girdiler, girdiler + 1
        # apad + -shortest: the output always has the full video length, even if speech ends earlier
        filtre = f"[{ses_no}:a]apad[mix]"
        if arka_plan is not None:
            komut += ["-i", str(arka_plan)]
            arka_no, girdiler = girdiler, girdiler + 1
            filtre = (f"[{arka_no}:a]volume={arka_plan_db}dB[bg];"
                      f"[{ses_no}:a][bg]amix=inputs=2:duration=longest:normalize=0,apad[mix]")
        komut += ["-filter_complex", filtre]
        ses_eslemesi = ["-map", "[mix]"]
    yumusak_altyazi = altyazi is not None and not yak
    if yumusak_altyazi:
        komut += ["-i", str(altyazi)]
        alt_no, girdiler = girdiler, girdiler + 1
    komut += ["-map", "0:v:0", *ses_eslemesi]
    if yak and altyazi is not None:
        komut += ["-vf", f"subtitles={_ffmpeg_filtre_yolu(Path(altyazi))}", "-c:v", "libx264", "-crf", "20",
                  "-preset", "medium", "-pix_fmt", "yuv420p"]
    else:
        komut += ["-c:v", "copy"]
    komut += ["-c:a", "aac", "-b:a", "192k"]
    if yumusak_altyazi:
        komut += ["-map", f"{alt_no}:s:0", "-c:s", "mov_text"]
    sure = _medya_suresi(video)  # output length = video length (padded speech, subtitles never cut the video)
    komut += (["-t", f"{sure:.3f}"] if sure else ["-shortest"]) + ["-movflags", "+faststart", str(gecici)]
    _calistir(komut)
    os.replace(gecici, hedef)
    if ai_etiketi and ses is not None:
        from dublaj_hatti.bolum_60_video_ve_encode.timeline_ve_final_encode.yapay_zeka_etiketi import (
            yapay_zeka_etiketi_ekle,
        )

        yapay_zeka_etiketi_ekle(hedef)
    return hedef


def _medya_suresi(yol: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    sonuc = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(yol)], capture_output=True, text=True, creationflags=NO_WINDOW)
    try:
        return float(sonuc.stdout.strip())
    except ValueError:
        return None


def _ffmpeg_filtre_yolu(yol: Path) -> str:
    """Path quoted for an ffmpeg filter argument (Windows drive colon and quotes escaped)."""
    metin = yol.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"'{metin}'"


def dubla(kaynak: str, hedef_klasor: str | Path | None = None, ayarlar: dict[str, Any] | None = None,
          lisans_onay: bool = False) -> dict[str, Any]:
    """The whole recommended flow in this process (same steps as ``dubla <video>``). Returns the result paths.

    The CLI adds a job store (resume, history) around the same call; use the CLI when you need those.
    """
    kaynak = kaynak_dogrula(kaynak)
    ek = dict(ayarlar or {})
    if hedef_klasor is not None:
        ek["genel.cikti_klasoru"] = str(hedef_klasor)
    ayar = _ayar(ek, genel__is_turu="dublaj")
    _lisans(secili_motorlar(ayar), lisans_onay)
    _hazirla(ayar)
    cfg = _cfg(ayar)
    from dublaj_hatti.bolum_00_omurga.core.dubber import full_dub_pipeline
    from dublaj_hatti.bolum_00_omurga.runtime.output_paths import get_output_root

    return full_dub_pipeline(kaynak, str(get_output_root(ayar["genel.cikti_klasoru"] or None)), cfg,
                             {"launch_method": "api"})
