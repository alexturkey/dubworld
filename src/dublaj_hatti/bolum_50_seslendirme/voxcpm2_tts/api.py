"""VoxCPM2 ile segment seslendirme (Supertonic ile ayni sonuc sozlesmesi)."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import soundfile as sf

from dublaj_hatti import ses_kitapligi
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.api import SupertonicDubResult, build_supertonic_audio_mix
from dublaj_hatti.bolum_50_seslendirme.supertonic_tts.execution import prepare_supertonic_result_for_segment
from dublaj_hatti.bolum_50_seslendirme.voxcpm2_tts.ayarlar import (
    VOXCPM2_COMMIT,
    VOXCPM2_VARSAYILAN_SES,
    voxcpm2_kok,
    voxcpm2_python,
)

VOXCPM2_ENGINE_ID = "voxcpm2"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
logger = logging.getLogger("dublaj_hatti")


class VoxCPM2Hatasi(RuntimeError):
    pass


def voxcpm2_durumu() -> Dict[str, Any]:
    kok = voxcpm2_kok()
    python = voxcpm2_python()
    kurulu = (kok / "ses_tasarim" / "motor.py").is_file() and python.is_file() and (kok / "ayarlar.json").is_file()
    return {"kurulu": kurulu, "kok": str(kok), "python": str(python), "commit": VOXCPM2_COMMIT}


def _segment_voice(seg, cfg) -> str:
    per_speaker = getattr(cfg, "voxcpm2_konusmaci_sesleri", None) or {}
    speaker = str(getattr(seg, "speaker", "") or "")
    # sıra: elle konuşmacı haritası > cinsiyete göre favori listeden atanan ses > tek ses
    return str(
        per_speaker.get(speaker)
        or getattr(seg, "voxcpm2_voice", "")
        or getattr(cfg, "voxcpm2_ses", "")
        or VOXCPM2_VARSAYILAN_SES
    )


def _run_engine(voice: str, parts: list, cfg, work_dir: Path) -> Dict[str, Any]:
    durum = voxcpm2_durumu()
    if not durum["kurulu"]:
        raise VoxCPM2Hatasi(
            "VoxCPM2 kurulu degil. Kurulum: scripts/kur.ps1 -Adim voxcpm2 (NVIDIA GPU gerekir). "
            f"Beklenen klasor: {durum['kok']}"
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    job_path = work_dir / "is.json"
    result_path = work_dir / "sonuc.json"
    job = {"ses": voice, "dil": cfg.target_lang, "calisma": str(work_dir), "parcalar": parts}
    if ses_kitapligi.kitaplik_mi(voice):  # kitaplik/<kimlik>: kullanicinin kendi sesi (rizali), yoksa yol gosteren hata
        job["kitaplik"] = ses_kitapligi.coz(voice)
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    command = [
        durum["python"], "-B", str(Path(__file__).with_name("kosucu.py")),
        "--kok", durum["kok"], "--is", str(job_path), "--sonuc", str(result_path),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW
    )
    if completed.returncode != 0 or not result_path.is_file():
        tail = (completed.stderr or completed.stdout or "")[-1500:]
        raise VoxCPM2Hatasi(f"VoxCPM2 kosucusu basarisiz (rc={completed.returncode}): {tail}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def build_voxcpm2_dubbed_audio(segments, cfg, run_dir: str) -> SupertonicDubResult:
    by_voice: Dict[str, list] = {}
    for seg in segments:
        by_voice.setdefault(_segment_voice(seg, cfg), []).append({"index": seg.index, "text": seg.text})

    raw_results: Dict[int, dict] = {}
    for number, (voice, parts) in enumerate(sorted(by_voice.items()), 1):
        logger.info("[VOXCPM2] ses=%s parca=%d", voice, len(parts))
        summary = _run_engine(voice, parts, cfg, Path(run_dir) / "voxcpm2" / f"ses_{number:02d}")
        if summary.get("hatali"):
            raise VoxCPM2Hatasi(f"VoxCPM2 su segmentleri bitiremedi (EOS yok): {summary['hatali'][:10]}")
        for index, path in summary["wavlar"].items():
            audio, rate = sf.read(path, dtype="float32")
            raw_results[int(index)] = {"wav_array": audio, "sample_rate": rate, "debug": {"voice_id": voice}}

    missing = [seg.index for seg in segments if seg.text.strip() and seg.index not in raw_results]
    if missing:
        raise VoxCPM2Hatasi(f"VoxCPM2 seslendirme eksik: {len(missing)} segment (ilk: {missing[:10]})")

    timing_infos, segment_audios, prepared = [], {}, {}
    for seg in segments:
        if seg.index not in raw_results:
            continue
        voice = raw_results[seg.index]["debug"]["voice_id"]
        idx, wav_array, timing_info, prepared_audio = prepare_supertonic_result_for_segment(
            seg, raw_results[seg.index], cfg.sample_rate, voice
        )
        timing_info["engine"] = VOXCPM2_ENGINE_ID
        segment_audios[idx] = wav_array
        timing_infos.append(timing_info)
        prepared[idx] = prepared_audio
    max_end = max((seg.end for seg in segments), default=0.0)
    mix = build_supertonic_audio_mix(prepared, max_end, cfg.sample_rate)
    return SupertonicDubResult(
        audio=mix, timing_infos=timing_infos, segment_audios=segment_audios, prepared_audios=prepared
    )
