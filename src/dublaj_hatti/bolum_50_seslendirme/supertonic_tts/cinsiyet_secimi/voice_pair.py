# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


FEMALE_SUPERTONIC_VOICES = {"F1", "F2", "F3", "F4", "F5"}
MALE_SUPERTONIC_VOICES = {"M1", "M2", "M3", "M4", "M5"}
AUTO_GENDER_PREFIX = "supertonic_auto_"


@dataclass(frozen=True)
class SupertonicVoicePair:
    female_voice_id: str
    male_voice_id: str
    fallback_voice_id: str


def normalize_voice_id(value: str) -> str:
    return str(value or "").strip().upper()


def build_auto_gender_tts_gender(female_voice_id: str, male_voice_id: str) -> str:
    pair = validate_voice_pair(female_voice_id, male_voice_id)
    return f"{AUTO_GENDER_PREFIX}{pair.female_voice_id}_{pair.male_voice_id}"


def parse_voice_pair_from_tts_gender(value: str) -> SupertonicVoicePair:
    raw = str(value or "").strip()
    if not raw.startswith(AUTO_GENDER_PREFIX):
        raise ValueError("Supertonic otomatik cinsiyet degeri degil")
    payload = raw[len(AUTO_GENDER_PREFIX):]
    parts = payload.split("_")
    if len(parts) != 2:
        raise ValueError("Supertonic otomatik cinsiyet degeri gecersiz")
    return validate_voice_pair(parts[0], parts[1])


def validate_voice_pair(female_voice_id: str, male_voice_id: str) -> SupertonicVoicePair:
    female = normalize_voice_id(female_voice_id)
    male = normalize_voice_id(male_voice_id)
    if female not in FEMALE_SUPERTONIC_VOICES:
        raise ValueError(f"Kadin Supertonic sesi gecersiz: {female_voice_id}")
    if male not in MALE_SUPERTONIC_VOICES:
        raise ValueError(f"Erkek Supertonic sesi gecersiz: {male_voice_id}")
    return SupertonicVoicePair(female_voice_id=female, male_voice_id=male, fallback_voice_id=female)
