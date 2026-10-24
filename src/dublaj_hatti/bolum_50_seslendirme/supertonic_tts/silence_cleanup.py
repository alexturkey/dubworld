import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np


SUPERTONIC_SILENCE_CLEANUP_POLICY = "unstable_silence_notes_v1"
SILENCE_LATENT_PATH = Path(__file__).with_name("unstable_silence_latent.json")
SILENCE_LATENT_SHA256 = "ed59fb6ce49b5582198a58fe070de644c208f27f4ac4a6077c64817d9011e1bb"
# Neden: kareler olcumle sessizlik < -95 dB / konusma > -50 dB / kararsiz arada ayrildi; tepeye 20 dB yakin kare aday olmaz. bkz. docs/engineering/pinned-values.md#supertonic-synthesis
FRAME_SILENT_BELOW_PEAK_DB = 45.0
CANDIDATE_BELOW_PEAK_DB = 20.0
NOTE_SILENT_MAX_DB = -95.0
NOTE_SPEECH_MIN_DB = -50.0
NOTE_REPEAT_FRAMES = 8
SILENT_NEIGHBOR_RADIUS = 2
UNSTABLE_CHAIN_ROUNDS = 3
NOTE_SILENT = 0
NOTE_UNSTABLE = 1
NOTE_SPEECH = 2


def get_silence_cleanup_profile():
    return {
        "policy": SUPERTONIC_SILENCE_CLEANUP_POLICY,
        "silence_latent_sha256": SILENCE_LATENT_SHA256,
        "frame_silent_below_peak_db": FRAME_SILENT_BELOW_PEAK_DB,
        "candidate_below_peak_db": CANDIDATE_BELOW_PEAK_DB,
        "note_silent_max_db": NOTE_SILENT_MAX_DB,
        "note_speech_min_db": NOTE_SPEECH_MIN_DB,
        "note_repeat_frames": NOTE_REPEAT_FRAMES,
        "silent_neighbor_radius": SILENT_NEIGHBOR_RADIUS,
        "unstable_chain_rounds": UNSTABLE_CHAIN_ROUNDS,
    }


@lru_cache(maxsize=1)
def load_silence_latent():
    raw = SILENCE_LATENT_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SILENCE_LATENT_SHA256:
        raise ValueError("Supertonic silence latent checksum mismatch")
    values = np.asarray(json.loads(raw.decode("ascii"))["values"], dtype=np.float32)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Invalid Supertonic silence latent")
    values.setflags(write=False)
    return values


def rms_db(blocks):
    power = np.mean(np.square(blocks, dtype=np.float64), axis=-1)
    return 20 * np.log10(np.maximum(np.sqrt(power), 1e-12))


def frame_levels_db(waveform, frames):
    samples = waveform.shape[-1]
    if waveform.ndim != 2 or waveform.shape[0] != 1 or samples < frames or samples % frames:
        raise ValueError("Supertonic waveform does not align with latent frames")
    return rms_db(waveform[0].reshape(frames, samples // frames))


def isolated_note_levels_db(latent, frames, vocode):
    notes = np.ascontiguousarray(np.repeat(latent[0][:, frames].T[:, :, None], NOTE_REPEAT_FRAMES, axis=2))
    rendered = np.asarray(vocode(notes))
    if rendered.ndim != 2 or rendered.shape[0] != len(frames) or rendered.shape[1] < 4:
        raise ValueError("Supertonic isolated note render shape mismatch")
    if not np.isfinite(rendered).all():
        raise ValueError("Nonfinite Supertonic isolated note render")
    quarter = rendered.shape[1] // 4
    return rms_db(rendered[:, quarter:rendered.shape[1] - quarter])


def classify_notes(levels_db):
    return np.where(
        levels_db < NOTE_SILENT_MAX_DB,
        NOTE_SILENT,
        np.where(levels_db > NOTE_SPEECH_MIN_DB, NOTE_SPEECH, NOTE_UNSTABLE),
    ).astype(np.int8)


def build_cleanup_mask(frame_db, note_class):
    count = len(note_class)
    silent = note_class == NOTE_SILENT
    unstable = note_class == NOTE_UNSTABLE
    mask = silent | (frame_db < frame_db.max() - FRAME_SILENT_BELOW_PEAK_DB)
    near_silent = np.zeros(count, dtype=bool)
    for offset in range(1, SILENT_NEIGHBOR_RADIUS + 1):
        near_silent[offset:] |= silent[:-offset]
        near_silent[:-offset] |= silent[offset:]
    mask |= unstable & near_silent
    for _ in range(UNSTABLE_CHAIN_ROUNDS):
        for frame in range(count):
            if unstable[frame] and not mask[frame] and (
                (frame > 0 and mask[frame - 1]) or (frame + 1 < count and mask[frame + 1])
            ):
                mask[frame] = True
    return mask


def clean_unstable_silence_notes(latent, waveform, vocode):
    silence = load_silence_latent()
    if latent.ndim != 3 or latent.shape[0] != 1 or latent.shape[1] != len(silence) or latent.shape[2] < 1:
        raise ValueError("Supertonic silence cleanup requires a single latent matching the silence note")
    frames = latent.shape[2]
    frame_db = frame_levels_db(waveform, frames)
    note_class = np.full(frames, NOTE_SPEECH, dtype=np.int8)
    candidates = np.flatnonzero(frame_db < frame_db.max() - CANDIDATE_BELOW_PEAK_DB)
    if len(candidates):
        note_class[candidates] = classify_notes(isolated_note_levels_db(latent, candidates, vocode))
    mask = build_cleanup_mask(frame_db, note_class)
    if not mask.any():
        return latent, mask
    cleaned = latent.copy()
    cleaned[0][:, mask] = silence[:, None]
    return cleaned, mask
