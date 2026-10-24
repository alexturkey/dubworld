# -*- coding: utf-8 -*-
import os
import logging
import asyncio

from .config import API_KEYS, DEFAULT_LANGUAGE

logger = logging.getLogger("dublaj_hatti")


def _get_api_key():
    if not API_KEYS:
        raise RuntimeError("SPEECHMATICS_API_KEY_1 .env dosyasinda bulunamadi")
    return API_KEYS[0]


def transcribe_audio(audio_path, language=None, use_diarization=False):
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(_transcribe_sync_wrapper, audio_path, language, use_diarization)
            return future.result()
    else:
        return asyncio.run(_transcribe_async(audio_path, language, use_diarization))


def _transcribe_sync_wrapper(audio_path, language, use_diarization):
    return asyncio.run(_transcribe_async(audio_path, language, use_diarization))


async def _transcribe_async(audio_path, language=None, use_diarization=False):
    from speechmatics.batch import AsyncClient, TranscriptionConfig

    api_key = _get_api_key()
    lang = language or DEFAULT_LANGUAGE

    logger.info("=" * 60)
    logger.info("[SPEECHMATICS] TRANSKRIPSIYON BASLIYOR")
    logger.info("[SPEECHMATICS] Ses dosyasi: %s", os.path.basename(audio_path))
    logger.info("[SPEECHMATICS] Dil: %s", lang)
    logger.info("[SPEECHMATICS] Diarization: %s", "ACIK" if use_diarization else "KAPALI")
    logger.info("=" * 60)

    client = AsyncClient(api_key=api_key)

    try:
        config_params = {"language": lang}
        if use_diarization:
            config_params["diarization"] = "speaker"

        job = await client.submit_job(
            audio_path,
            transcription_config=TranscriptionConfig(**config_params),
        )
        logger.info("[SPEECHMATICS] Job gonderildi: %s", job.id)

        result = await client.wait_for_completion(job.id)
        logger.info("[SPEECHMATICS] Job tamamlandi: %s", job.id)

        words, detected_language = _parse_result(result, lang)

        if use_diarization:
            unique_speakers = set(w["speaker"] for w in words if w["speaker"])
            logger.info("[SPEECHMATICS] %d kelime, %d konusmaci tespit edildi", len(words), len(unique_speakers))
        else:
            logger.info("[SPEECHMATICS] %d kelime tespit edildi", len(words))
        logger.info("=" * 60)

        raw_transcript = getattr(result, "transcript_text", "") or ""

        return {
            "success": True,
            "words": words,
            "detected_language": detected_language,
            "total_words": len(words),
            "raw_transcript": raw_transcript,
        }

    except Exception as e:
        logger.error("[SPEECHMATICS] Hata: %s", str(e))
        return {
            "success": False,
            "error": str(e),
            "words": [],
            "detected_language": language or "en",
            "total_words": 0,
        }
    finally:
        await client.close()


def _normalize_speaker(speaker_label):
    if not speaker_label:
        return ""
    label = speaker_label.strip()
    if label.startswith("S") and label[1:].isdigit():
        idx = int(label[1:]) - 1
        return f"SPEAKER_{idx:02d}"
    return label


def _parse_result(result, language):
    detected_language = language
    words = []

    for item in result.results:
        if not item.alternatives:
            continue
        alt = item.alternatives[0]
        word_lang = getattr(alt, "language", "") or ""
        if word_lang and detected_language in ("auto", ""):
            detected_language = word_lang

        raw_speaker = getattr(alt, "speaker", "") or ""
        speaker = _normalize_speaker(raw_speaker)

        if item.type == "word":
            words.append({
                "word": alt.content,
                "start": float(item.start_time if hasattr(item, "start_time") else 0),
                "end": float(item.end_time if hasattr(item, "end_time") else 0),
                "speaker": speaker,
            })
        elif item.type == "punctuation" and words:
            words[-1]["word"] += alt.content

    logger.info("[SPEECHMATICS] Tespit edilen dil: %s", detected_language)

    return words, detected_language
