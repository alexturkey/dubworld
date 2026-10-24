# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env", encoding="utf-8-sig", override=False)

API_KEYS = []

_key1 = os.getenv("SPEECHMATICS_API_KEY_1", "")
if _key1:
    API_KEYS.append(_key1)

_key2 = os.getenv("SPEECHMATICS_API_KEY_2", "")
if _key2:
    API_KEYS.append(_key2)

BATCH_URL = "https://asr.api.speechmatics.com/v2"

DEFAULT_LANGUAGE = "en"
