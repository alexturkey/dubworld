from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


project_root = Path(__file__).resolve().parents[4]
load_dotenv(project_root / ".env", encoding="utf-8-sig", override=False)

engine_id = "elevenlabs_scribe_v2"
engine_display_name = "ElevenLabs Scribe v2"
model_id = "scribe_v2"
endpoint = "https://api.elevenlabs.io/v1/speech-to-text"
price_usd_per_audio_hour = 0.22
pricing_source = "https://elevenlabs.io/pricing/api?price.section=speech_to_text"
limits_source = "https://elevenlabs.io/docs/overview/capabilities/speech-to-text/"
maximum_file_bytes = 3_000_000_000
maximum_audio_seconds = 36_000.0
request_timeout_seconds = 1800
minimum_upload_bytes_per_second = 65_536
upload_timeout_grace_seconds = 60
exchange_rate_timeout_seconds = 10.0
account_status_timeout_seconds = 15.0
analytics_timeout_seconds = 10.0
analytics_retry_count = 3
analytics_retry_delay_seconds = 1.0


def get_api_key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "").strip()
