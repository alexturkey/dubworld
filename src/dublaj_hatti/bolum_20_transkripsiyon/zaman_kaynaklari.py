"""Which component produces the source-side word times for each transcription engine (data only, stdlib only).

Single table behind docs/engineering/timing-sources.md and tests/test_zaman_kaynaklari.py. It describes what the code
does; it does not choose anything at run time (the engine is chosen in ``yapilandirma.stt_secimi_coz``).

Kaynak türleri / source kinds:
- ``ctc_kutusu``: shared CTC box ``bolum_30_hizalama_ve_segment/ctc_kelime_hizalama`` (wav2vec2 via WhisperX 3.8.6,
  ``ctc_speech_bounded_v2``); the engine only supplies text + time windows.
- ``whisperx_hizalama``: WhisperX's own ``whisperx.align()`` inside the WhisperX worker (same wav2vec2 CTC family).
- ``whisper_dogal``: Whisper cross-attention word timestamps (faster-whisper ``word_timestamps=True``), no CTC.
- ``model_dogal``: the model's own word times (CrisperWhisper Medium attention heads, Moonshine native timestamps).
- ``saglayici``: word times returned by a cloud provider's API (your own key).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZamanKaynagi:
    motor: str
    kaynak: str  # see module docstring
    pencere_kaniti: str  # what the engine hands to the aligner as time evidence ("-" when no aligner runs)
    kod: tuple[str, ...]  # files (relative to src/dublaj_hatti) where the word times are produced
    not_: str = ""

    @property
    def ctc(self) -> bool:
        return self.kaynak in ("ctc_kutusu", "whisperx_hizalama")


CTC_KUTUSU = "bolum_30_hizalama_ve_segment/ctc_kelime_hizalama/client.py"

ZAMAN_KAYNAKLARI: dict[str, ZamanKaynagi] = {
    z.motor: z
    for z in (
        ZamanKaynagi("faster-whisper", "whisper_dogal", "-",
                     ("bolum_20_transkripsiyon/faster_whisper_motoru/worker.py",),
                     "explicit choice only: Whisper's own word times are kept on purpose; auto never resolves here"),
        ZamanKaynagi("faster_whisper_ctc", "ctc_kutusu", "faster-whisper segments (native word times diagnostic only)",
                     ("bolum_00_omurga/core/dubber.py",),
                     "auto falls back here when CrisperWhisper Turbo is not usable; a missing CTC model stops the job"),
        ZamanKaynagi("whisperx", "whisperx_hizalama", "ASR segments",
                     ("bolum_20_transkripsiyon/whisperx_motoru/worker.py",),
                     "segment_sync without diarization: recognition and alignment run as two checkpointed stages"),
        ZamanKaynagi("crisperwhisper_turbo_ct2", "ctc_kutusu", "native word times (diagnostic) -> windows",
                     ("bolum_00_omurga/runtime/crisperwhisper_turbo_ct2_runtime.py",),
                     "native times kept only for diagnostics; repair budget shared with json3"),
        ZamanKaynagi("crisperwhisper2_medium", "model_dogal", "-",
                     ("bolum_00_omurga/runtime/crisperwhisper_runtime.py",)),
        ZamanKaynagi("moonshine_medium_streaming_en", "model_dogal", "-",
                     ("bolum_00_omurga/runtime/moonshine_medium_streaming_runtime.py",),
                     "experimental: backwards starts stop the run (MoonshineDeneyselHatasi), times never edited"),
        ZamanKaynagi("whisper_cpp_cpu_align", "ctc_kutusu", "whisper.cpp segments",
                     ("bolum_20_transkripsiyon/whisper_cpp_cpu_align_motoru/ctc_alignment_runner.py",)),
        ZamanKaynagi("parakeet_cpu_align", "ctc_kutusu", "token times; gaps >= 1.0 s split windows (80 ms pad)",
                     ("bolum_20_transkripsiyon/parakeet_cpu_align_motoru/alignment_runner.py",)),
        ZamanKaynagi("speechmatics", "saglayici", "-",
                     ("bolum_20_transkripsiyon/speechmatics_motoru/engine.py",)),
        ZamanKaynagi("elevenlabs_scribe_v2", "saglayici", "-",
                     ("bolum_20_transkripsiyon/elevenlabs_scribe_v2_motoru/engine.py",)),
        ZamanKaynagi("youtube_translate", "ctc_kutusu", "json3 start hints (never final times)",
                     ("bolum_20_transkripsiyon/youtube_json3_kaynagi/engine.py",),
                     "text from the YouTube automatic json3 caption track; no speech recognition"),
    )
}


def zaman_kaynagi(motor: str) -> ZamanKaynagi:
    """Timing source of a resolved engine name (resolve ``auto`` first with ``yapilandirma.stt_secimi_coz``)."""
    try:
        return ZAMAN_KAYNAKLARI[motor]
    except KeyError:
        raise KeyError(f"unknown transcription engine for timing table: {motor!r} (resolve 'auto' first)") from None
