"""pipeline_checkpoint birim testleri (GPU'suz; kaynak projedeki test_pipeline_checkpoint karşılığı).

Hattın tamamını koşturan testler (dubber + model) burada yok; mağaza, devam seçenekleri ve kopyalama sözleşmesi sınanır.
Seslendirme paketine (psutil vb.) dokunan sözleşme testleri yalnız tam kurulumda koşar.
"""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from dublaj_hatti.bolum_00_omurga.core import pipeline_checkpoint as pipeline_checkpoint_module
from dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint import (
    DEFAULT_LARGE_FILE_THRESHOLD,
    FULL_TEXT_CHECKPOINT_STAGES,
    SEGMENT_SYNC_CHECKPOINT_STAGES,
    PipelineCheckpointError,
    PipelineCheckpointLockedError,
    PipelineCheckpointStore,
    canonical_json_hash,
    checkpoint_resume_options,
    clone_checkpoint_for_resume,
)

try:
    from dublaj_hatti.bolum_00_omurga.core.pipeline_selection_contract import segment_translation_checkpoint_inputs
    from dublaj_hatti.bolum_50_seslendirme.supertonic_tts import SUPERTONIC_SYNTHESIS_CONTRACT
    SES_PAKETI = True
except ImportError:  # yalın CI ortamı (--no-deps)
    SES_PAKETI = False

ses_paketi_gerekli = pytest.mark.skipif(not SES_PAKETI, reason="seslendirme bağımlılıkları kurulu değil")


def _store(tmp_path: Path, event_callback=None) -> PipelineCheckpointStore:
    return PipelineCheckpointStore(
        tmp_path / "run",
        pipeline_kind="segment_sync",
        source_identity="https://example.test/video",
        job_id=42,
        event_callback=event_callback,
    )


def test_canonical_hash_is_order_independent():
    assert canonical_json_hash({"a": 1, "b": 2}) == canonical_json_hash({"b": 2, "a": 1})


def test_manifest_is_bomless_and_completed_stage_restores(tmp_path):
    store = _store(tmp_path)
    artifact = store.run_dir / "source.wav"
    artifact.write_bytes(b"audio")
    store.begin_stage("source_audio", 3, 1, {"video": "v1"})
    store.complete_stage("source_audio", {"audio": "source.wav"}, [artifact])

    assert not store.state_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert store.can_restore("source_audio", 3, 1, {"video": "v1"}) is True
    assert store.stage_payload("source_audio") == {"audio": "source.wav"}


def test_manifest_atomic_write_retries_transient_windows_permission_error(tmp_path):
    real_replace = os.replace
    calls = {"count": 0}

    def transient_replace(source, target):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise PermissionError(5, "transient file lock")
        return real_replace(source, target)

    with patch("dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint.os.replace", side_effect=transient_replace):
        store = _store(tmp_path)

    assert calls["count"] == 3
    assert store.state_path.is_file()
    assert json.loads(store.state_path.read_text(encoding="utf-8"))["job_id"] == "42"


def test_manifest_atomic_write_keeps_permanent_permission_error_visible(tmp_path):
    with patch("dublaj_hatti.bolum_00_omurga.core.pipeline_checkpoint.os.replace", side_effect=PermissionError(5, "permanent lock")) as replace_mock:
        with pytest.raises(PermissionError, match="permanent lock"):
            _store(tmp_path)

    assert replace_mock.call_count == 5


def test_ready_artifact_event_is_emitted_only_after_file_exists(tmp_path):
    events = []
    store = _store(tmp_path, events.append)
    transcript = store.run_dir / "translated_segments_tr.txt"

    with pytest.raises(PipelineCheckpointError):
        store.emit_artifact_ready("bilingual_dubbing_transcript", transcript)

    transcript.write_text("[EN] Source.\n[TR] Turkce.", encoding="utf-8")
    store.emit_artifact_ready("bilingual_dubbing_transcript", transcript)

    assert events[-1]["event"] == "artifact_ready"
    assert events[-1]["artifact_kind"] == "bilingual_dubbing_transcript"
    assert events[-1]["artifact_path"] == str(transcript.resolve())


def test_changed_artifact_invalidates_stage_and_following_stages(tmp_path):
    store = _store(tmp_path)
    first = store.run_dir / "source.wav"
    second = store.run_dir / "transcript.json"
    first.write_bytes(b"audio")
    second.write_text("{}", encoding="utf-8")
    store.begin_stage("source_audio", 3, 1, {"video": "v1"})
    store.complete_stage("source_audio", {}, [first])
    store.begin_stage("transcription", 6, 1, {"audio": "v1"})
    store.complete_stage("transcription", {}, [second])

    first.write_bytes(b"changed-audio")

    assert store.can_restore("source_audio", 3, 1, {"video": "v1"}) is False
    assert "source_audio" not in store.state["stages"]
    assert "transcription" not in store.state["stages"]


@pytest.mark.parametrize("extension", [".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus"])
def test_critical_audio_extensions_always_use_full_sha256(tmp_path, monkeypatch, extension):
    monkeypatch.setattr(pipeline_checkpoint_module, "DEFAULT_LARGE_FILE_THRESHOLD", 1)
    artifact = tmp_path / f"critical_audio{extension}"
    artifact.write_bytes(b"audio")

    record = pipeline_checkpoint_module._file_digest(artifact)

    assert record["digest_mode"] == "full_sha256"


def test_large_wav_middle_corruption_with_preserved_size_and_mtime_invalidates_stage(tmp_path):
    store = _store(tmp_path)
    artifact = store.run_dir / "large_timeline.wav"
    artifact_size = DEFAULT_LARGE_FILE_THRESHOLD + 4 * 1024 * 1024
    with artifact.open("wb") as stream:
        stream.truncate(artifact_size)
        stream.seek(0)
        stream.write(b"RIFF")
        stream.seek(artifact_size - 4)
        stream.write(b"data")
    store.begin_stage("timeline_audio", 13, 1, {"source": "tts"})
    store.complete_stage("timeline_audio", {}, [artifact])
    record = store.state["stages"]["timeline_audio"]["artifacts"][0]
    original_stat = artifact.stat()

    with artifact.open("r+b") as stream:
        stream.seek(artifact_size // 2)
        stream.write(b"BROKEN")
    os.utime(artifact, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert artifact.stat().st_size == artifact_size
    assert artifact.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert record["digest_mode"] == "full_sha256"
    assert store.can_restore("timeline_audio", 13, 1, {"source": "tts"}) is False


@ses_paketi_gerekli
def test_resume_options_stop_before_deleted_recorded_artifact(tmp_path):
    store = _store(tmp_path)
    first_stage, second_stage = SEGMENT_SYNC_CHECKPOINT_STAGES[:2]
    artifacts = []
    for stage_id, stage_order, contract_version in (first_stage, second_stage):
        artifact = store.run_dir / f"{stage_order:02d}_{stage_id}.bin"
        artifact.write_bytes(stage_id.encode("utf-8"))
        inputs = {"stage": stage_id}
        if stage_id == "full_text_tek_ses_tts":
            inputs["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, {"artifact": artifact.name}, [artifact])
        artifacts.append(artifact)

    assert [item["stage_id"] for item in checkpoint_resume_options(store.run_dir)] == [
        first_stage[0],
        second_stage[0],
    ]

    artifacts[1].unlink()

    assert [item["stage_id"] for item in checkpoint_resume_options(store.run_dir)] == [first_stage[0]]


def test_changed_inputs_or_contract_invalidates_downstream(tmp_path):
    store = _store(tmp_path)
    store.begin_stage("asr_audio", 5, 1, {"demucs": False})
    store.complete_stage("asr_audio")
    store.begin_stage("transcription", 6, 1, {"model": "turbo"})
    store.complete_stage("transcription")

    assert store.can_restore("asr_audio", 5, 1, {"demucs": True}) is False
    assert store.state["stages"] == {}

    store.begin_stage("asr_audio", 5, 1, {"demucs": True})
    store.complete_stage("asr_audio")
    assert store.can_restore("asr_audio", 5, 2, {"demucs": True}) is False


def test_decoder_profile_change_invalidates_transcription_but_preserves_prior_audio(tmp_path):
    store = _store(tmp_path)
    store.begin_stage("asr_sesi_hazirlama", 5, 1, {"audio": "source.wav"})
    store.complete_stage("asr_sesi_hazirlama")
    old_inputs = {
        "engine": "whisperx",
        "model_name": "large-v3-turbo",
        "compute_type": "float32",
        "decoder_profile": "whisperx_engine_default_v1",
    }
    store.begin_stage("transkripsiyon", 6, 1, old_inputs)
    store.complete_stage("transkripsiyon")
    new_inputs = {
        **old_inputs,
        "decoder_profile": "whisperx_float32_quality_v1",
    }

    assert store.can_restore("transkripsiyon", 6, 1, new_inputs) is False
    assert "asr_sesi_hazirlama" in store.state["stages"]
    assert "transkripsiyon" not in store.state["stages"]


def test_failed_stage_is_not_restored_and_keeps_error(tmp_path):
    store = _store(tmp_path)
    store.begin_stage("translation", 9, 1, {"target": "tr"})
    store.fail_stage("translation", RuntimeError("network failed"))

    assert store.can_restore("translation", 9, 1, {"target": "tr"}) is False
    assert store.state["status"] == "running"
    assert store.state["failed_stage"] == ""


def test_skipped_stage_is_explicit_and_restorable(tmp_path):
    store = _store(tmp_path)
    store.skip_stage("demucs", 4, 1, {"enabled": False}, "disabled_by_user")

    assert store.can_restore("demucs", 4, 1, {"enabled": False}) is True
    assert store.stage_payload("demucs")["skip_reason"] == "disabled_by_user"


def test_pipeline_lock_rejects_second_live_owner(tmp_path):
    first = _store(tmp_path)
    second = _store(tmp_path)
    first.acquire()
    try:
        with pytest.raises(PipelineCheckpointLockedError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_dead_process_lock_is_reclaimed(tmp_path):
    store = _store(tmp_path)
    store.lock_path.write_text(
        json.dumps({"token": "old", "pid": 99999999, "host": "test", "created_at": "old"}),
        encoding="utf-8",
    )

    store.acquire()
    assert store.lock_path.exists()
    store.release()
    assert not store.lock_path.exists()


def test_source_or_job_identity_mismatch_is_rejected(tmp_path):
    _store(tmp_path)
    with pytest.raises(PipelineCheckpointError):
        PipelineCheckpointStore(
            tmp_path / "run",
            pipeline_kind="segment_sync",
            source_identity="different-source",
            job_id=42,
        )
    with pytest.raises(PipelineCheckpointError):
        PipelineCheckpointStore(
            tmp_path / "run",
            pipeline_kind="segment_sync",
            source_identity="https://example.test/video",
            job_id=43,
        )


def test_events_report_stage_lifecycle(tmp_path):
    events = []
    store = _store(tmp_path, events.append)
    store.begin_stage("source", 1, 1, {"source": "url"})
    store.complete_stage("source")
    store.mark_pipeline_completed()

    assert [event["event"] for event in events] == [
        "stage_started",
        "stage_completed",
        "pipeline_completed",
    ]


def test_event_callback_failure_does_not_mask_checkpoint_state(tmp_path):
    def failing_callback(event):
        raise RuntimeError("database unavailable")

    store = _store(tmp_path, failing_callback)
    store.acquire()
    store.begin_stage("source", 1, 1, {"source": "url"})
    store.complete_stage("source")
    store.release()

    assert store.state["last_completed_stage"] == "source"
    assert not store.lock_path.exists()


@pytest.mark.parametrize(
    ("pipeline_kind", "stage_sequence"),
    [
        ("segment_sync", SEGMENT_SYNC_CHECKPOINT_STAGES),
        pytest.param("full_text", FULL_TEXT_CHECKPOINT_STAGES, marks=ses_paketi_gerekli),
    ],
)
def test_every_checkpoint_stage_preserves_prior_and_invalidates_downstream(
    tmp_path,
    pipeline_kind,
    stage_sequence,
):
    for failure_index, (failed_stage_id, failed_order, failed_contract) in enumerate(stage_sequence):
        run_dir = tmp_path / f"{pipeline_kind}_{failure_index}"
        store = PipelineCheckpointStore(
            run_dir,
            pipeline_kind=pipeline_kind,
            source_identity="stage-matrix",
            job_id=failure_index + 1,
        )
        artifact_paths = {}
        for stage_id, stage_order, contract_version in stage_sequence:
            artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
            artifact.write_text(json.dumps({"stage_id": stage_id}), encoding="utf-8")
            artifact_paths[stage_id] = artifact
            store.begin_stage(stage_id, stage_order, contract_version, {"stage_id": stage_id})
            store.complete_stage(stage_id, {"stage_id": stage_id}, [artifact])

        artifact_paths[failed_stage_id].write_text("changed", encoding="utf-8")

        assert store.can_restore(
            failed_stage_id,
            failed_order,
            failed_contract,
            {"stage_id": failed_stage_id},
        ) is False
        remaining = set(store.state["stages"])
        assert remaining == {stage_id for stage_id, _, _ in stage_sequence[:failure_index]}


def test_store_relocates_with_renamed_run_directory(tmp_path):
    store = _store(tmp_path)
    store.acquire()
    renamed = tmp_path / "renamed_run"
    os.rename(store.run_dir, renamed)
    store.relocate(renamed)

    assert store.state_path == renamed / "pipeline_state.json"
    assert store.lock_path == renamed / ".pipeline_execution.lock"
    store.release()
    assert not store.lock_path.exists()


def test_checkpoint_clone_preserves_original_and_stops_after_selected_stage(tmp_path):
    store = _store(tmp_path)
    first = store.run_dir / "02_video.mp4"
    second = store.run_dir / "03_audio.wav"
    downstream = store.run_dir / "06_transcript.json"
    first.write_bytes(b"video")
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, {"source": "url"})
    store.complete_stage("video_indirme_veya_kopyalama", {"video": first.name}, [first])
    second.write_bytes(b"audio")
    store.begin_stage("kaynak_ses_cikarma", 3, 1, {"video": first.name})
    store.complete_stage("kaynak_ses_cikarma", {"audio": second.name}, [second])
    downstream.write_text("{}", encoding="utf-8")
    store.begin_stage("transkripsiyon", 6, 1, {"audio": second.name})
    store.fail_stage("transkripsiyon", "test failure")

    cloned = clone_checkpoint_for_resume(store.run_dir, 99, "kaynak_ses_cikarma")

    assert store.state_path.exists()
    assert downstream.exists()
    assert cloned != store.run_dir
    assert (cloned / first.name).read_bytes() == b"video"
    assert (cloned / second.name).read_bytes() == b"audio"
    assert not (cloned / downstream.name).exists()
    cloned_state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    assert cloned_state["job_id"] == "99"
    assert cloned_state["resume_source_job_id"] == "42"
    assert cloned_state["resume_after_stage"] == "kaynak_ses_cikarma"
    assert set(cloned_state["stages"]) == {
        "video_indirme_veya_kopyalama",
        "kaynak_ses_cikarma",
    }
    assert [item["stage_id"] for item in checkpoint_resume_options(cloned)] == [
        "video_indirme_veya_kopyalama",
        "kaynak_ses_cikarma",
    ]


def test_checkpoint_clone_rejects_noncontiguous_or_running_selection(tmp_path):
    store = _store(tmp_path)
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, {"source": "url"})
    store.complete_stage("video_indirme_veya_kopyalama")
    store.begin_stage("kaynak_ses_cikarma", 3, 1, {"video": "v"})

    with pytest.raises(PipelineCheckpointError, match="kullanilamaz"):
        clone_checkpoint_for_resume(store.run_dir, 99, "kaynak_ses_cikarma")


def test_checkpoint_clone_is_idempotent_and_cleans_stale_preparation(tmp_path):
    store = _store(tmp_path)
    artifact = store.run_dir / "source.mp4"
    artifact.write_bytes(b"video")
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, {"source": "url"})
    store.complete_stage("video_indirme_veya_kopyalama", {"video": artifact.name}, [artifact])
    expected_target = clone_checkpoint_for_resume(store.run_dir, 99, "video_indirme_veya_kopyalama")
    stale_temporary = store.run_dir.parent / f".{expected_target.name}.hazirlaniyor"
    shutil.rmtree(expected_target)
    stale_temporary.mkdir()
    (stale_temporary / "partial.bin").write_bytes(b"partial")

    first = clone_checkpoint_for_resume(store.run_dir, 99, "video_indirme_veya_kopyalama")
    second = clone_checkpoint_for_resume(store.run_dir, 99, "video_indirme_veya_kopyalama")

    assert first == expected_target
    assert second == first
    assert not stale_temporary.exists()


def test_checkpoint_clone_target_name_is_ascii_and_bounded(tmp_path):
    long_name = "çğışöü" * 12
    run_dir = tmp_path / long_name
    store = PipelineCheckpointStore(run_dir, "segment_sync", "unicode-source", 42)
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, {"source": "url"})
    store.complete_stage("video_indirme_veya_kopyalama")

    cloned = clone_checkpoint_for_resume(run_dir, 99, "video_indirme_veya_kopyalama")

    assert cloned.name.isascii()
    assert len(cloned.name) < 150


def test_checkpoint_clone_rejects_corrupt_existing_target(tmp_path):
    store = _store(tmp_path)
    artifact = store.run_dir / "source.mp4"
    artifact.write_bytes(b"video")
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, {"source": "url"})
    store.complete_stage("video_indirme_veya_kopyalama", {"video": artifact.name}, [artifact])
    cloned = clone_checkpoint_for_resume(store.run_dir, 99, "video_indirme_veya_kopyalama")
    (cloned / artifact.name).write_bytes(b"corrupt")

    with pytest.raises(PipelineCheckpointError, match="Mevcut devam kopyasi bozuk"):
        clone_checkpoint_for_resume(store.run_dir, 99, "video_indirme_veya_kopyalama")


@ses_paketi_gerekli
@pytest.mark.parametrize(
    ("pipeline_kind", "stage_sequence"),
    [
        ("segment_sync", SEGMENT_SYNC_CHECKPOINT_STAGES),
        ("full_text", FULL_TEXT_CHECKPOINT_STAGES),
    ],
)
def test_every_checkpoint_can_create_a_cumulative_verified_clone(tmp_path, pipeline_kind, stage_sequence):
    run_dir = tmp_path / f"source_{pipeline_kind}"
    store = PipelineCheckpointStore(run_dir, pipeline_kind, "cumulative-source", 500)
    artifacts = []
    for stage_id, stage_order, contract_version in stage_sequence:
        artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
        artifact.write_text(json.dumps({"stage": stage_id}), encoding="utf-8")
        artifacts.append(artifact)
        inputs = {"stage": stage_id}
        if stage_id == "full_text_tek_ses_tts":
            inputs["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, {"artifact": artifact.name}, [artifact])

    for selected_index, (selected_stage_id, _, _) in enumerate(stage_sequence):
        cloned = clone_checkpoint_for_resume(run_dir, 600 + selected_index, selected_stage_id)
        options = checkpoint_resume_options(cloned)
        assert [item["stage_id"] for item in options] == [
            stage_id for stage_id, _, _ in stage_sequence[:selected_index + 1]
        ]
        for artifact_index, artifact in enumerate(artifacts):
            assert (cloned / artifact.name).exists() is (artifact_index <= selected_index)


@ses_paketi_gerekli
def test_clone_normalizes_legacy_disabled_demucs_without_invalidating_downstream(tmp_path):
    run_dir = tmp_path / "legacy_disabled_demucs"
    store = PipelineCheckpointStore(run_dir, "full_text", "legacy-source", 41)
    for stage_id, stage_order, contract_version in FULL_TEXT_CHECKPOINT_STAGES:
        if stage_order > 10:
            break
        inputs = {"stage": stage_id}
        if stage_id == "full_text_tek_ses_tts":
            inputs["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        if stage_id == "demucs_vokal_ayirma":
            inputs = {
                "source_audio_path": "source_audio.wav",
                "enabled": False,
                "model": "htdemucs",
                "prepare_asr_ready": True,
            }
            store.skip_stage(stage_id, stage_order, contract_version, inputs, "disabled_by_configuration")
            continue
        artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"stage": stage_id}), encoding="utf-8")
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, {"artifact": artifact.name}, [artifact])

    cloned = clone_checkpoint_for_resume(run_dir, 42, "full_text_final_altyazi_alignment")
    cloned_state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    demucs_stage = cloned_state["stages"]["demucs_vokal_ayirma"]
    expected_inputs = {
        "source_audio_path": "source_audio.wav",
        "enabled": False,
        "model": "htdemucs",
        "prepare_asr_ready": False,
    }
    assert demucs_stage["inputs"] == expected_inputs
    assert demucs_stage["input_hash"] == canonical_json_hash(expected_inputs)
    verifier = PipelineCheckpointStore(cloned, "full_text", "legacy-source", 42)
    demucs_contract_version = next(
        contract_version
        for stage_id, _, contract_version in FULL_TEXT_CHECKPOINT_STAGES
        if stage_id == "demucs_vokal_ayirma"
    )
    assert verifier.can_restore("demucs_vokal_ayirma", 4, demucs_contract_version, expected_inputs) is True
    assert "full_text_final_altyazi_alignment" in verifier.state["stages"]


@ses_paketi_gerekli
def test_clone_normalizes_legacy_supertonic_translation_for_voice_independent_reuse(tmp_path):
    run_dir = tmp_path / "legacy_supertonic_translation"
    store = PipelineCheckpointStore(run_dir, "segment_sync", "legacy-translation-source", 71)
    for stage_id, stage_order, contract_version in SEGMENT_SYNC_CHECKPOINT_STAGES:
        if stage_order > 10:
            break
        inputs = {"stage": stage_id}
        if stage_id == "ceviri":
            inputs = {
                "source_segments_hash": "segments",
                "source_lang": "en",
                "target_lang": "tr",
                "translator_engine": "codex_bridge",
                "bridge_backend": "codex",
                "tts_engine": "supertonic",
                "tts_voice_id": "F3",
                "tts_speed_factor": 1.2,
                "supertonic_flow_mode": "natural_blocks_1",
            }
        artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"stage": stage_id}), encoding="utf-8")
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, {"artifact": artifact.name}, [artifact])

    cloned = clone_checkpoint_for_resume(run_dir, 72, "ses_yonlendirme")
    cloned_state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    expected_inputs = segment_translation_checkpoint_inputs(
        source_segments_hash="segments",
        source_lang="en",
        target_lang="tr",
        translator_engine="codex_bridge",
        bridge_backend="codex",
        tts_engine="supertonic",
        tts_voice_id="F3",
        tts_speed_factor=1.2,
        supertonic_flow_mode="natural_blocks_1",
    )
    translation_stage = cloned_state["stages"]["ceviri"]
    assert translation_stage["inputs"] == expected_inputs
    assert translation_stage["input_hash"] == canonical_json_hash(expected_inputs)
    verifier = PipelineCheckpointStore(cloned, "segment_sync", "legacy-translation-source", 72)
    assert verifier.can_restore("ceviri", 9, 2, expected_inputs) is True
    assert verifier.can_restore("ses_yonlendirme", 10, 2, {"stage": "ses_yonlendirme"}) is True


@ses_paketi_gerekli
def test_clone_normalizes_legacy_full_text_visual_inputs_when_smart_frame_was_unused(tmp_path):
    run_dir = tmp_path / "legacy_full_text_visual"
    store = PipelineCheckpointStore(run_dir, "full_text", "legacy-visual-source", 51)
    for stage_id, stage_order, contract_version in FULL_TEXT_CHECKPOINT_STAGES:
        if stage_order > 10:
            break
        inputs = {"stage": stage_id}
        if stage_id == "full_text_tek_ses_tts":
            inputs["supertonic_synthesis_contract"] = SUPERTONIC_SYNTHESIS_CONTRACT
        payload = {}
        if stage_id == "video_indirme_veya_kopyalama":
            inputs = {"source": "legacy-visual-source"}
            payload = {"video_path": "video_run.mp4", "video_title": "Legacy", "source_lang": "en"}
        elif stage_id == "full_text_final_altyazi_alignment":
            inputs = {
                "subtitle_mode": "segment",
                "tts_manifest_path": "pipeline_full_text_tts_result/manifest.json",
            }
        artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"stage": stage_id}), encoding="utf-8")
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, payload, [artifact])

    cloned = clone_checkpoint_for_resume(run_dir, 52, "full_text_final_altyazi_alignment")
    cloned_state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    visual_stage = cloned_state["stages"]["full_text_final_altyazi_alignment"]
    expected_inputs = {
        "subtitle_mode": "segment",
        "tts_manifest_path": "pipeline_full_text_tts_result/manifest.json",
        "smart_frame_capture_enabled": False,
        "source_video_path": "video_run.mp4",
    }
    assert visual_stage["inputs"] == expected_inputs
    assert visual_stage["input_hash"] == canonical_json_hash(expected_inputs)
    verifier = PipelineCheckpointStore(cloned, "full_text", "legacy-visual-source", 52)
    assert verifier.can_restore("full_text_final_altyazi_alignment", 10, 1, expected_inputs) is True


def test_clone_normalizes_legacy_segment_visual_inputs_when_smart_frame_was_unused(tmp_path):
    run_dir = tmp_path / "legacy_segment_visual"
    store = PipelineCheckpointStore(run_dir, "segment_sync", "legacy-segment-source", 61)
    for stage_id, stage_order, contract_version in SEGMENT_SYNC_CHECKPOINT_STAGES:
        if stage_order > 12:
            break
        inputs = {"stage": stage_id}
        payload = {}
        if stage_id == "video_indirme_veya_kopyalama":
            inputs = {"source": "legacy-segment-source"}
            payload = {"video_path": "video_run.mp4", "video_title": "Legacy", "source_lang": "en"}
        elif stage_id == "altyazi_hazirlama":
            inputs = {
                "subtitle_mode": "segment",
                "tts_engine": "supertonic",
                "target_lang": "tr",
                "tts_manifest_path": "pipeline_tts_result/manifest.json",
            }
        artifact = run_dir / f"{stage_order:02d}_{stage_id}.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"stage": stage_id}), encoding="utf-8")
        store.begin_stage(stage_id, stage_order, contract_version, inputs)
        store.complete_stage(stage_id, payload, [artifact])

    cloned = clone_checkpoint_for_resume(run_dir, 62, "altyazi_hazirlama")
    cloned_state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    visual_stage = cloned_state["stages"]["altyazi_hazirlama"]
    expected_inputs = {
        "subtitle_mode": "segment",
        "tts_engine": "supertonic",
        "target_lang": "tr",
        "tts_manifest_path": "pipeline_tts_result/manifest.json",
        "smart_frame_capture_enabled": False,
        "source_video_path": "video_run.mp4",
    }
    assert visual_stage["inputs"] == expected_inputs
    assert visual_stage["input_hash"] == canonical_json_hash(expected_inputs)
    verifier = PipelineCheckpointStore(cloned, "segment_sync", "legacy-segment-source", 62)
    assert verifier.can_restore("altyazi_hazirlama", 12, 1, expected_inputs) is True


def test_legacy_smart_frame_resume_recovers_raw_video_before_audio_checkpoints(tmp_path):
    run_dir = tmp_path / "legacy_smart_frame"
    run_dir.mkdir()
    raw_video = run_dir / "video.mp4"
    cropped_video = run_dir / "video_smart_frame.mp4"
    source_audio = run_dir / "source.wav"
    raw_video.write_bytes(b"raw-video")
    cropped_video.write_bytes(b"cropped-video")
    (run_dir / "smart_frame_analysis.json").write_text(
        json.dumps({"input_path": str(raw_video.resolve())}),
        encoding="utf-8",
    )
    store = PipelineCheckpointStore(run_dir, "segment_sync", "https://example.test/legacy", 41)
    source_inputs = {
        "source": "https://example.test/legacy",
        "smart_frame_capture_enabled": True,
        "smart_frame_algorithm_version": "legacy",
    }
    store.begin_stage("video_indirme_veya_kopyalama", 2, 1, source_inputs)
    store.complete_stage(
        "video_indirme_veya_kopyalama",
        {
            "video_path": cropped_video.name,
            "video_title": "Legacy",
            "source_lang": "en",
            "smart_frame_capture": {"enabled": True, "crop_applied": True},
        },
        [cropped_video],
    )
    source_audio.write_bytes(b"audio")
    audio_inputs = {
        "video_path": cropped_video.name,
        "use_demucs": False,
        "sample_rate": 16000,
        "channels": 1,
    }
    store.begin_stage("kaynak_ses_cikarma", 3, 1, audio_inputs)
    store.complete_stage(
        "kaynak_ses_cikarma",
        {"source_audio_path": source_audio.name},
        [source_audio],
    )

    cloned = clone_checkpoint_for_resume(run_dir, 42, "kaynak_ses_cikarma")
    state = json.loads((cloned / "pipeline_state.json").read_text(encoding="utf-8"))
    source_stage = state["stages"]["video_indirme_veya_kopyalama"]
    audio_stage = state["stages"]["kaynak_ses_cikarma"]
    assert source_stage["payload"]["video_path"] == "video.mp4"
    assert "smart_frame_capture" not in source_stage["payload"]
    assert source_stage["inputs"] == {"source": "https://example.test/legacy"}
    assert audio_stage["inputs"]["video_path"] == "video.mp4"
    assert (cloned / "video.mp4").read_bytes() == b"raw-video"



