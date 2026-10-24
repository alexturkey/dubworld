"""Tam hat devam testleri (GPU'suz): kaynak projedeki test_pipeline_checkpoint'in hattı uçtan uca koşturan
bölümü. Ağır adımlar (kaynak indirme, ses çıkarma, STT, çeviri, TTS, video) sahte işlevlerle değiştirilir;
`full_dub_pipeline` gerçekten çalışır ve devamda önceki aşamaların yeniden çalışmadığı sayılarak doğrulanır.
Seslendirme bağımlılıkları (numpy vb.) kurulu değilse modül atlanır.
"""

import ast
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

np = pytest.importorskip("numpy")
dubber_modulu = pytest.importorskip("dublaj_hatti.bolum_00_omurga.core.dubber")

import dublaj_hatti.bolum_00_omurga.runtime.internet_gateway.gateway as internet_gateway_module  # noqa: E402
from dublaj_hatti.bolum_00_omurga.core.dubber import (  # noqa: E402
    DubConfig,
    _run_full_text_dub_after_transcription,
    _shift_timed_item_for_asr_offset,
    check_global_word_overlaps,
    full_dub_pipeline,
)
from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (  # noqa: E402
    FULL_TEXT_CHECKPOINT_STAGES,
    SEGMENT_SYNC_CHECKPOINT_STAGES,
    PipelineCheckpointStore,
    canonical_json_hash,
)
from dublaj_hatti.bolum_00_omurga.full_metin_dublaji import FullTextAudioChunk, FullTextSynthesis  # noqa: E402
from dublaj_hatti.bolum_20_transkripsiyon.whisperx_motoru import decoder_profiles  # noqa: E402
from dublaj_hatti.bolum_30_hizalama_ve_segment.nihai_dublaj_segmentleri import NihaiDublajSegmenti  # noqa: E402
from dublaj_hatti.bolum_50_seslendirme.tts_orkestratoru.service import TTSBuildResult  # noqa: E402


def test_asr_offset_normalizes_floating_point_zero_residue():
    item = {"start": 1.0000000000000022, "end": 1.56}

    changed = _shift_timed_item_for_asr_offset(item, 1.0)

    assert changed is True
    assert item == {"start": 0.0, "end": 0.56}


def test_global_word_overlap_tolerates_floating_point_boundary_residue(tmp_path):
    alignment = {
        "segments": [
            {
                "words": [
                    {"word": ".md.", "start": 661.0, "end": 661.3800000000001},
                    {"word": "when", "start": 661.38, "end": 661.6},
                ]
            }
        ]
    }

    check_global_word_overlaps(alignment, str(tmp_path), "source.wav")

    timeline = (tmp_path / "global_word_timeline.txt").read_text(encoding="utf-8")
    assert "Tolerans Icinde Esit Sayilan Sinir: 1" in timeline
    assert "Overlap Durumu: YOK" in timeline


def test_global_word_overlap_rejects_real_one_millisecond_overlap(tmp_path):
    alignment = {
        "segments": [
            {
                "words": [
                    {"word": "first", "start": 0.0, "end": 1.001},
                    {"word": "second", "start": 1.0, "end": 1.5},
                ]
            }
        ]
    }

    with pytest.raises(RuntimeError, match="1 adet overlap tespit edildi"):
        check_global_word_overlaps(alignment, str(tmp_path), "source.wav")


def test_whisperx_contract_bump_does_not_change_non_whisper_checkpoint_fingerprint(monkeypatch):
    def fingerprint(engine: str, model_name: str, compute_type: str) -> str:
        return canonical_json_hash({
            "engine": engine,
            "model_name": model_name,
            "compute_type": compute_type,
            "decoder_profile": decoder_profiles.resolve_transcription_decoder_profile(
                engine,
                model_name,
                compute_type,
            ),
            "decoder_contract_version": decoder_profiles.transcription_decoder_contract_version(engine),
        })

    parakeet_before = fingerprint(
        "parakeet_cpu_align",
        "parakeet-unified-en-0.6b-int8",
        "int8",
    )
    whisperx_before = fingerprint("whisperx", "large-v3-turbo", "float32")
    monkeypatch.setattr(
        decoder_profiles,
        "WHISPERX_DECODER_CONTRACT_VERSION",
        decoder_profiles.WHISPERX_DECODER_CONTRACT_VERSION + 1,
    )

    assert fingerprint(
        "parakeet_cpu_align",
        "parakeet-unified-en-0.6b-int8",
        "int8",
    ) == parakeet_before
    assert fingerprint("whisperx", "large-v3-turbo", "float32") != whisperx_before


def test_resume_run_dir_cannot_escape_output_root(tmp_path, monkeypatch):
    output_root = tmp_path / "output"
    outside_run = tmp_path / "outside"
    output_root.mkdir()
    outside_run.mkdir()
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(output_root))

    with pytest.raises(ValueError, match="output kokunun disinda"):
        full_dub_pipeline(
            "https://example.test/video",
            str(output_root),
            DubConfig(),
            {"codex_bridge_backend": "codex", "resume_run_dir": str(outside_run)},
        )


def test_stage_contract_registry_matches_dubber_calls():
    tree = ast.parse((Path(dubber_modulu.__file__)).read_text(encoding="utf-8"))
    observed = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"can_restore", "begin_stage", "skip_stage"} or len(node.args) < 3:
            continue
        values = []
        for argument in node.args[:3]:
            if not isinstance(argument, ast.Constant):
                break
            values.append(argument.value)
        if len(values) == 3 and isinstance(values[0], str):
            observed.add(tuple(values))

    expected = set(SEGMENT_SYNC_CHECKPOINT_STAGES) | set(FULL_TEXT_CHECKPOINT_STAGES)
    assert observed == expected


def test_full_pipeline_resumes_at_failed_transcription_without_repeating_prior_stages(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path))
    initial_run_dir = tmp_path / "run_ornek"
    initial_run_dir.mkdir()
    events = []
    calls = {"source": 0, "audio": 0, "asr": 0, "transcription": 0}

    def prepare_source(source, run_dir, logger=None):
        calls["source"] += 1
        video_path = Path(run_dir) / "video.mp4"
        video_path.write_bytes(b"video")
        return str(video_path), "Test Video", "en"

    def extract_source(video_path, cfg, run_dir):
        calls["audio"] += 1
        audio_path = Path(run_dir) / "source_audio.wav"
        audio_path.write_bytes(b"audio")
        return str(audio_path)

    def prepare_asr(audio_path, cfg, run_dir):
        calls["asr"] += 1
        return audio_path, 0.0

    def transcribe(*args, **kwargs):
        calls["transcription"] += 1
        if calls["transcription"] == 1:
            raise RuntimeError("injected transcription failure")
        segment = NihaiDublajSegmenti(index=0, start=0.0, end=1.0, text="hello")
        return [segment], "en", {"segments": []}

    cfg = DubConfig(dubbing_mode="full_text", use_demucs=False)
    metadata = {"job_id": 77, "codex_bridge_backend": "codex", "pipeline_event_callback": events.append}
    patches = (
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.ensure_run_dir", return_value=str(initial_run_dir)),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_source_video", side_effect=prepare_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._extract_source_audio", side_effect=extract_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._prepare_audio_for_asr_transcription", side_effect=prepare_asr),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.transcribe_and_align", side_effect=transcribe),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.log_video_metadata"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._run_full_text_dub_after_transcription", return_value={"dubbed_video": "done.mp4"}),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        with pytest.raises(RuntimeError, match="injected transcription failure"):
            full_dub_pipeline("https://example.test/video", str(tmp_path), cfg, metadata)

        run_dir = next(tmp_path.glob("test_video_*"))
        failed_state = json.loads((run_dir / "pipeline_state.json").read_text(encoding="utf-8"))
        assert failed_state["failed_stage"] == "transkripsiyon"

        resumed_metadata = {
            "job_id": 77,
            "codex_bridge_backend": "codex",
            "resume_run_dir": str(run_dir),
            "pipeline_event_callback": events.append,
        }
        result = full_dub_pipeline(
            "https://example.test/video",
            str(tmp_path),
            DubConfig(dubbing_mode="full_text", use_demucs=False),
            resumed_metadata,
        )

    assert result == {"dubbed_video": "done.mp4"}
    assert calls == {"source": 1, "audio": 1, "asr": 1, "transcription": 2}
    assert any(event["event"] == "stage_restored" for event in events)


def test_network_path_switch_retries_current_checkpoint_without_restarting_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DUBLAJ_EGRESS_PROXY", "http://127.0.0.1:40002")
    monkeypatch.setenv("DUBLAJ_EGRESS_MODE", "direct")
    for proxy_env_name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(proxy_env_name, raising=False)
    internet_gateway_module._GATEWAY = None
    initial_run_dir = tmp_path / "run_ornek"
    initial_run_dir.mkdir()
    calls = {"source": 0, "audio": 0, "asr": 0, "transcription": 0}

    def prepare_source(source, run_dir, logger=None):
        calls["source"] += 1
        video_path = Path(run_dir) / "video.mp4"
        video_path.write_bytes(b"video")
        return str(video_path), "Gateway Video", "en"

    def extract_source(video_path, cfg, run_dir):
        calls["audio"] += 1
        audio_path = Path(run_dir) / "source_audio.wav"
        audio_path.write_bytes(b"audio")
        return str(audio_path)

    def prepare_asr(audio_path, cfg, run_dir):
        calls["asr"] += 1
        return audio_path, 0.0

    def transcribe(*args, **kwargs):
        calls["transcription"] += 1
        if calls["transcription"] == 1:
            raise OSError(11004, "getaddrinfo failed")
        assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:40002"
        segment = NihaiDublajSegmenti(index=0, start=0.0, end=1.0, text="hello")
        return [segment], "en", {"segments": []}

    cfg = DubConfig(dubbing_mode="full_text", use_demucs=False)
    patches = (
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.ensure_run_dir", return_value=str(initial_run_dir)),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_source_video", side_effect=prepare_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._extract_source_audio", side_effect=extract_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._prepare_audio_for_asr_transcription", side_effect=prepare_asr),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.transcribe_and_align", side_effect=transcribe),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.log_video_metadata"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._run_full_text_dub_after_transcription", return_value={"dubbed_video": "done.mp4"}),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = full_dub_pipeline(
            "https://example.test/video",
            str(tmp_path),
            cfg,
            {"job_id": 107, "codex_bridge_backend": "codex"},
        )

    run_dir = next(tmp_path.glob("gateway_video_*"))
    state = json.loads((run_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run_dir / "internet_gateway_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result == {"dubbed_video": "done.mp4"}
    assert calls == {"source": 1, "audio": 1, "asr": 1, "transcription": 2}
    assert state["stages"]["transkripsiyon"]["status"] == "completed"
    assert events[-1]["operation"] == "transkripsiyon"
    assert events[-1]["action"] == "retry_same_operation"
    internet_gateway_module._GATEWAY = None


def test_smart_frame_source_stage_always_preserves_raw_video(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path))
    observed_video_paths = []

    for enabled in (False, True):
        case_root = tmp_path / ("enabled" if enabled else "disabled")
        case_root.mkdir()
        initial_run_dir = case_root / "run_ornek"
        initial_run_dir.mkdir()

        def prepare_source(source, run_dir, logger=None):
            video_path = Path(run_dir) / "video.mp4"
            video_path.write_bytes(b"source")
            return str(video_path), "Smart Frame Video", "en"

        def apply_smart_frame(source_path, work_dir, enabled=True, logger=None):
            cropped_path = Path(work_dir) / "video_smart_frame.mp4"
            analysis_path = Path(work_dir) / "smart_frame_analysis.json"
            preview_path = Path(work_dir) / "smart_frame_preview.jpg"
            cropped_path.write_bytes(b"cropped")
            analysis_path.write_text("{}", encoding="utf-8")
            preview_path.write_bytes(b"preview")
            return {
                "status": "cropped",
                "enabled": True,
                "crop_applied": True,
                "reason": "content_box_detected",
                "video_path": str(cropped_path),
                "analysis_path": str(analysis_path),
                "preview_path": str(preview_path),
                "crop_info": {"filter": "crop=1080:616:0:830"},
            }

        def extract_source(video_path, cfg, run_dir):
            observed_video_paths.append((enabled, Path(video_path).name))
            raise RuntimeError("stop after source stage")

        with patch("dublaj_hatti.bolum_00_omurga.core.dubber.ensure_run_dir", return_value=str(initial_run_dir)):
            with patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_source_video", side_effect=prepare_source):
                with patch("dublaj_hatti.bolum_10_kaynak_edinme.akilli_kare_yakalama.apply_smart_frame_capture", side_effect=apply_smart_frame) as apply_mock:
                    with patch("dublaj_hatti.bolum_00_omurga.core.dubber._extract_source_audio", side_effect=extract_source):
                        with patch("dublaj_hatti.bolum_00_omurga.core.dubber.log_video_metadata"):
                            cfg = DubConfig(
                                dubbing_mode="full_text",
                                use_demucs=False,
                                smart_frame_capture_enabled=enabled,
                            )
                            with pytest.raises(RuntimeError, match="stop after source stage"):
                                full_dub_pipeline(
                                    f"https://example.test/smart-frame-{enabled}",
                                    str(case_root),
                                    cfg,
                                    {"job_id": 900 + int(enabled), "codex_bridge_backend": "codex"},
                                )

        assert apply_mock.call_count == 0
        run_dir = next(case_root.glob("smart_frame_video_*"))
        state = json.loads((run_dir / "pipeline_state.json").read_text(encoding="utf-8"))
        source_stage = state["stages"]["video_indirme_veya_kopyalama"]
        assert source_stage["status"] == "completed"
        assert "smart_frame_capture" not in source_stage["payload"]
        assert source_stage["payload"]["video_path"] == "video.mp4"

    assert observed_video_paths == [
        (False, "video.mp4"),
        (True, "video.mp4"),
    ]


def test_tts_failure_resume_does_not_repeat_translation_or_prior_stages(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path))
    initial_run_dir = tmp_path / "run_ornek"
    initial_run_dir.mkdir()
    calls = {"source": 0, "audio": 0, "asr": 0, "transcription": 0, "translation": 0, "tts": 0}

    def prepare_source(source, run_dir, logger=None):
        calls["source"] += 1
        path = Path(run_dir) / "video.mp4"
        path.write_bytes(b"video")
        return str(path), "Segment Video", "en"

    def extract_source(video_path, cfg, run_dir):
        calls["audio"] += 1
        path = Path(run_dir) / "source_audio.wav"
        path.write_bytes(b"audio")
        return str(path)

    def prepare_asr(audio_path, cfg, run_dir):
        calls["asr"] += 1
        return audio_path, 0.0

    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]

    def transcribe(*args, **kwargs):
        calls["transcription"] += 1
        raw = NihaiDublajSegmenti(index=0, start=0.0, end=0.9, text="hello world", words=words)
        return [raw], "en", {"segments": [{"start": 0.0, "end": 0.9, "text": "hello world", "words": words}]}

    class Translator:
        last_video_usage_report = ""

        def translate_segments(self, segments, run_dir):
            calls["translation"] += 1
            return ["merhaba dünya" for _ in segments]

    def build_tts(segments, cfg, run_dir):
        calls["tts"] += 1
        if calls["tts"] == 1:
            raise RuntimeError("injected tts failure")
        audio = np.zeros(2400, dtype=np.float32)
        return TTSBuildResult(
            audio=audio,
            timing_infos=[{"segment_index": 1, "tts_processed_duration": 0.1}],
            segment_audios={1: audio},
        )

    cfg = DubConfig(dubbing_mode="segment_sync", target_lang="en", use_demucs=False)
    metadata = {"job_id": 88, "codex_bridge_backend": "codex"}
    patches = (
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.ensure_run_dir", return_value=str(initial_run_dir)),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_source_video", side_effect=prepare_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._extract_source_audio", side_effect=extract_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._prepare_audio_for_asr_transcription", side_effect=prepare_asr),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.transcribe_and_align", side_effect=transcribe),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.log_video_metadata"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_transcripts"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_full_paragraph"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_word_level_transcript"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_source_subtitle_preview", return_value={}),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.check_global_word_overlaps"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._create_segment_translator", side_effect=lambda *args, **kwargs: Translator()),
        # kaynaktaki edge/supertonic/xtts otomatik cinsiyet yardımcılarının repodaki tek karşılığı
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._apply_konusmaci_basina_ses_if_needed"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.build_dubbed_audio", side_effect=build_tts),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_one_pass_subtitle_assets", side_effect=RuntimeError("stop after tts")),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14]:
        with pytest.raises(RuntimeError, match="injected tts failure"):
            full_dub_pipeline("https://example.test/segment", str(tmp_path), cfg, metadata)

        run_dir = next(tmp_path.glob("segment_video_*"))
        resumed_metadata = {"job_id": 88, "codex_bridge_backend": "codex", "resume_run_dir": str(run_dir)}
        with pytest.raises(RuntimeError, match="stop after tts"):
            full_dub_pipeline(
                "https://example.test/segment",
                str(tmp_path),
                DubConfig(dubbing_mode="segment_sync", target_lang="en", use_demucs=False),
                resumed_metadata,
            )

    assert calls == {
        "source": 1,
        "audio": 1,
        "asr": 1,
        "transcription": 1,
        "translation": 1,
        "tts": 2,
    }


def test_whisperx_alignment_failure_resume_does_not_repeat_transcription(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBLAJ_OUTPUT_DIR", str(tmp_path))
    initial_run_dir = tmp_path / "run_ornek"
    initial_run_dir.mkdir()
    calls = {"source": 0, "audio": 0, "asr": 0, "transcription": 0, "alignment": 0}
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]

    def prepare_source(source, run_dir, logger=None):
        calls["source"] += 1
        path = Path(run_dir) / "video.mp4"
        path.write_bytes(b"video")
        return str(path), "Align Video", "en"

    def extract_source(video_path, cfg, run_dir):
        calls["audio"] += 1
        path = Path(run_dir) / "source_audio.wav"
        path.write_bytes(b"audio")
        return str(path)

    def prepare_asr(audio_path, cfg, run_dir):
        calls["asr"] += 1
        return audio_path, 0.0

    def transcribe(*args, **kwargs):
        calls["transcription"] += 1
        raw = NihaiDublajSegmenti(index=0, start=0.0, end=0.9, text="hello world")
        return [raw], "en", {"segments": []}

    def align(*args, **kwargs):
        calls["alignment"] += 1
        if calls["alignment"] == 1:
            raise RuntimeError("injected alignment failure")
        aligned = NihaiDublajSegmenti(index=0, start=0.0, end=0.9, text="hello world", words=words)
        return [aligned], {"segments": [{"start": 0.0, "end": 0.9, "text": "hello world", "words": words}]}, str(Path(args[4]) / "alignment_input.json")

    patches = (
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.ensure_run_dir", return_value=str(initial_run_dir)),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_source_video", side_effect=prepare_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._extract_source_audio", side_effect=extract_source),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._prepare_audio_for_asr_transcription", side_effect=prepare_asr),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.transcribe_and_align", side_effect=transcribe),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._align_whisperx_checkpoint_segments", side_effect=align),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.log_video_metadata"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_transcripts"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_full_paragraph"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_word_level_transcript"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.write_source_subtitle_preview", return_value={}),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber.check_global_word_overlaps"),
        patch("dublaj_hatti.bolum_00_omurga.core.dubber._create_segment_translator", side_effect=RuntimeError("stop after alignment")),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
        cfg = DubConfig(dubbing_mode="segment_sync", transcription_engine="whisperx", target_lang="en")
        with pytest.raises(RuntimeError, match="injected alignment failure"):
            full_dub_pipeline("https://example.test/alignment", str(tmp_path), cfg, {"job_id": 99, "codex_bridge_backend": "codex"})
        run_dir = next(tmp_path.glob("align_video_*"))
        with pytest.raises(RuntimeError, match="stop after alignment"):
            full_dub_pipeline(
                "https://example.test/alignment",
                str(tmp_path),
                DubConfig(dubbing_mode="segment_sync", transcription_engine="whisperx", target_lang="en"),
                {"job_id": 99, "codex_bridge_backend": "codex", "resume_run_dir": str(run_dir)},
            )

    assert calls == {"source": 1, "audio": 1, "asr": 1, "transcription": 1, "alignment": 2}


def test_full_text_tts_failure_resume_does_not_repeat_single_codex_translation(tmp_path):
    calls = {"translation": 0, "tts": 0}
    video_path = tmp_path / "source.mp4"
    video_path.write_bytes(b"video")
    segments = [NihaiDublajSegmenti(index=1, start=1.0, end=3.0, text="hello world")]

    class Translator:
        last_video_usage_report = ""

        def __init__(self, *args, **kwargs):
            pass

        def translate_full_text(self, text, run_dir):
            calls["translation"] += 1
            return "merhaba dünya"

    def synthesize(*args, **kwargs):
        calls["tts"] += 1
        if calls["tts"] == 1:
            raise RuntimeError("injected full text tts failure")
        audio = np.zeros(2400, dtype=np.float32)
        return FullTextSynthesis(
            audio=audio,
            sample_rate=24000,
            chunk_count=1,
            actual_chunks=(FullTextAudioChunk("merhaba dünya", audio),),
            inter_chunk_silence_samples=0,
        )

    checkpoint = PipelineCheckpointStore(
        tmp_path,
        pipeline_kind="full_text",
        source_identity="full-text-test",
        job_id=123,
    )
    config = DubConfig(
        dubbing_mode="full_text",
        tts_engine="supertonic",
        translator_engine="codex_bridge",
        target_lang="tr",
        full_text_duration_fit_mode="video_to_audio",
    )
    with patch("dublaj_hatti.bolum_00_omurga.core.dubber.FullTextBridgeTranslator", Translator), \
         patch("dublaj_hatti.bolum_00_omurga.core.dubber.synthesize_full_text_supertonic", side_effect=synthesize), \
         patch("dublaj_hatti.bolum_00_omurga.core.dubber.save_wave"), \
         patch("dublaj_hatti.bolum_00_omurga.core.dubber.prepare_one_pass_subtitle_assets", side_effect=RuntimeError("stop after full text tts")):
        with pytest.raises(RuntimeError, match="injected full text tts failure"):
            _run_full_text_dub_after_transcription(
                str(video_path),
                str(tmp_path / "source.wav"),
                None,
                segments,
                "en",
                config,
                str(tmp_path),
                {"codex_bridge_backend": "codex"},
                checkpoint,
            )
        with pytest.raises(RuntimeError, match="stop after full text tts"):
            _run_full_text_dub_after_transcription(
                str(video_path),
                str(tmp_path / "source.wav"),
                None,
                segments,
                "en",
                config,
                str(tmp_path),
                {"codex_bridge_backend": "codex"},
                checkpoint,
            )

    assert calls == {"translation": 1, "tts": 2}
