"""Konusmaciya ses atama: tahmin edilen cinsiyete gore havuz, elle harita oncelikli."""

from __future__ import annotations

# Neden: siniflandiricinin 'bilinmiyor' sinifi yok; bilinmeyen cinsiyet kadin havuzuna duser. bkz. docs/engineering/pinned-values.md#supertonic-voices
FEMALE_VOICE_POOL = ["F1", "F2", "F3", "F4", "F5"]
MALE_VOICE_POOL = ["M1", "M2", "M3", "M4", "M5"]
VALID_VOICES = set(FEMALE_VOICE_POOL + MALE_VOICE_POOL)


def assign_voice_ids_to_speakers(
    speaker_gender_map: dict[str, dict],
    manual_voice_map: dict[str, str] | None = None,
    female_pool: list[str] | None = None,
    male_pool: list[str] | None = None,
) -> dict[str, dict]:
    """Havuz verilmezse Supertonic (F1..F5 / M1..M5, elle ses buyuk harfe cevrilir ve dogrulanir).

    Havuz verilirse (VoxCPM2: kullanicinin kadin / erkek favori listeleri) ses adi serbest metindir
    ("hazir/<ad>", "<ad>/<cesit>", klasor yolu); elle verilen her bos olmayan ses gecerlidir.
    """
    supertonic = female_pool is None and male_pool is None
    if supertonic:
        manual = {str(k): str(v).strip().upper() for k, v in (manual_voice_map or {}).items()}
        female_pool, male_pool = FEMALE_VOICE_POOL, MALE_VOICE_POOL
    else:
        manual = {str(k): str(v).strip() for k, v in (manual_voice_map or {}).items() if str(v).strip()}
        female_pool = list(female_pool or male_pool or [])
        male_pool = list(male_pool or female_pool)
        if not female_pool:
            raise ValueError("kadin ve erkek ses havuzu bos")
    female = [v for v in female_pool if v not in manual.values()] or female_pool
    male = [v for v in male_pool if v not in manual.values()] or male_pool
    female_index = 0
    male_index = 0
    result = {}
    for speaker in sorted(speaker_gender_map):
        gender = str(speaker_gender_map[speaker].get("gender") or "unknown")
        decision_source = speaker_gender_map[speaker].get("decision_source", "")
        if speaker in manual and (not supertonic or manual[speaker] in VALID_VOICES):
            voice_id = manual[speaker]
            decision_source = "manual"
        elif gender == "male":
            voice_id = male[male_index % len(male)]
            male_index += 1
        else:
            voice_id = female[female_index % len(female)]
            female_index += 1
        result[speaker] = {
            "speaker": speaker,
            "gender": gender,
            "voice_id": voice_id,
            "confidence": speaker_gender_map[speaker].get("confidence", 0.0),
            "decision_source": decision_source,
        }
    return result
