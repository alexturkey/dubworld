from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

try:
    from .natural_blocks_chain_contract import (
        build_natural_blocks_review_retry_job,
        is_natural_blocks_job,
        natural_blocks_review_violations,
        replace_natural_blocks_retry_result,
    )
except ImportError:
    from natural_blocks_chain_contract import (
        build_natural_blocks_review_retry_job,
        is_natural_blocks_job,
        natural_blocks_review_violations,
        replace_natural_blocks_retry_result,
    )

try:
    from .istem_guvenligi import VERI_TALIMAT_AYRIMI, cikti_enjeksiyon_ihlalleri
except ImportError:
    from istem_guvenligi import VERI_TALIMAT_AYRIMI, cikti_enjeksiyon_ihlalleri

try:
    from . import hedef_dil
except ImportError:
    import hedef_dil

# Konsol penceresi acmadan alt surec (Windows); diger sistemlerde 0.
NO_WINDOW_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# Zaman aşımında yalnız doğrudan çocuk (node.exe) değil bütün ağaç kapanır: aksi halde codex.exe ve araç
# süreçleri (node_repl) iş düştükten sonra da açık kalıyordu. İş başına toplam bütçe: yeniden deneme çağrıları
# da --timeout içinde kalır, orkestratörün dış zaman aşımından önce temiz hata verilir.
_IS_BITIS: float | None = None
EN_AZ_CAGRI_SURESI = 30


def is_butcesi_baslat(timeout_seconds: int) -> None:
    global _IS_BITIS
    _IS_BITIS = time.time() + max(1, int(timeout_seconds))


def kalan_sure(timeout_seconds: int) -> int:
    if _IS_BITIS is None:
        return int(timeout_seconds)
    return max(EN_AZ_CAGRI_SURESI, min(int(timeout_seconds), int(_IS_BITIS - time.time())))


def surec_agacini_kapat(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=NO_WINDOW_FLAGS, check=False)
    else:
        proc.kill()


def agacli_calistir(command: list[str], *, input_text: str, timeout: int, **kwargs: Any) -> subprocess.CompletedProcess:
    """subprocess.run(capture_output=True, text=True) eşdeğeri; zaman aşımında süreç ağacını kapatır."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", **kwargs)
    try:
        stdout, stderr = proc.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        surec_agacini_kapat(proc)
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = "", ""
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from None
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


BRIDGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BRIDGE_ROOT.parents[3]
RUNTIME_ROOT = BRIDGE_ROOT / "runtime"
# Calisma durumu (inbox/outbox/logs/tmp/usage, status.json) her zaman runtime/ altinda: .gitignore disinda tutulur ve
# claude_code_cli kopruyle ayni duzen. Eskiden runtime/ yoksa kaynak klasorune yaziliyordu (iş metni git'e girebilirdi).
WORK_ROOT = RUNTIME_ROOT
INBOX_DIR = WORK_ROOT / "inbox"
PROCESSING_DIR = WORK_ROOT / "processing"
OUTBOX_DIR = WORK_ROOT / "outbox"
FAILED_DIR = WORK_ROOT / "failed"
LOGS_DIR = WORK_ROOT / "logs"
TMP_DIR = WORK_ROOT / "tmp"
USAGE_DIR = WORK_ROOT / "usage"
API_USAGE_EVENTS_FILE = USAGE_DIR / "api_usage_events.jsonl"
API_USAGE_SUMMARY_FILE = USAGE_DIR / "api_usage_summary.json"
PROMPT_FILE = BRIDGE_ROOT / "backends" / "codex_exec" / "prompt.md"
CODEX_BACKEND_CONFIG_FILE = BRIDGE_ROOT / "backends" / "codex_exec" / "backend_config.json"
DEFAULT_GEMINI_PROMPT_FILE = BRIDGE_ROOT / "backends" / "gemini_2_5_flash" / "prompt.md"
RESULT_SCHEMA = BRIDGE_ROOT / "backends" / "codex_exec" / "output_schema.json"
DEFAULT_GEMINI_31_FLASH_LITE_PROMPT_FILE = BRIDGE_ROOT / "backends" / "gemini_3_1_flash_lite_tier_1" / "prompt.md"
CODEX_SESSION_ROOT = Path.home() / ".codex" / "sessions"
MAX_CONTRACT_RETRIES = 2
MAX_NATURAL_BLOCKS_CHAIN_REVIEW_RETRIES = 1
MAX_JOB_ID_MISMATCH_RETRIES = 1
MAX_FULL_TEXT_PARTIAL_RETRIES = 2
FULL_TEXT_HIGH_REASONING_WORD_THRESHOLD = 6000
MAX_ACCEPTED_CANDIDATES = 10
DEFAULT_CANDIDATE_COUNT = 7
DEFAULT_CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_CODEX_REASONING_EFFORT = "medium"
CODEX_PRICED_MODELS = {"gpt-5.6-luna"}
VALID_CODEX_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}
CODEX_EXEC_WORK_DIR = Path(tempfile.gettempdir()) / "dublaj_hatti_codex_exec"
CODEX_EXEC_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "goals",
    "hooks",
    "image_generation",
    "in_app_browser",
    "multi_agent",
    "personality",
    "plugins",
    "remote_plugin",
    "shell_snapshot",
    "shell_tool",
    "skill_mcp_dependency_install",
    "skill_search",
    "tool_suggest",
    "workspace_dependencies",
)
CODEX_SAVED_LOGIN_BLOCKED_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY")
ASR_CONTEXTUAL_CORRECTION_PROMPT = """ASR BAGLAMSAL DUZELTME SOZLESMESI:
- Kaynak metin otomatik konusma tanima sisteminin duyma tahminidir; yazimi ve noktalama isaretlerini mutlak dogru kabul etme.
- Ceviriden once kaynakta anlatilmak isteneni sessizce yeniden kur. Full Metin isinde source_text alaninin tamamini; segment isinde discourse_context.ordered_source_text, context_before, ana segmentler ve context_after alanlarini birlikte kullan.
- Yalniz yuksek guvenli ve baglamla kanitlanan ASR hatalarini duzelt: yanlis duyulan kelime veya harf, kisaltma, ozel ad, teknik terim, homofon, buyuk-kucuk harf, noktalama ve segment sinirinda bolunen ifade.
- Kanit onceligi: acik ad veya acilim ile kisaltmanin harfleri; ayni terimin metnin baska yerindeki temiz tekrari; konu ve komsu cumlelerle desteklenen bilinen ad veya teknik terim; dilbilgisel butunluk. Yalniz ses benzerligi tek basina yeterli kanit degildir.
- Ornek: Metnin baska yerinde LLM geciyorsa veya baglam Large Language Model kavramini acikca destekliyorsa ASR'nin LNM yazimini LLM olarak yorumla. Bu ornegi kapali bir sozluk sayma; ayni kanit yontemini diger adlara, kisaltmalara ve kelimelere de uygula.
- Birden fazla makul yorum varsa kelime, isim, sayi veya teknik terim uydurma. Belirsizligi koruyan sadik bir ceviri yap.
- Baglami yalniz hatayi anlamak icin kullan. Ceviri gerektirmeyen komsu segmentlerin anlamini ana segmente tasima; segment sahipligini ve id eslesmesini koru.
- Ciktida ASR hatasini veya bu denetimi aciklama. Istenen JSON semasini koru ve ceviride kaynak sesin baglamla kanitlanan asil anlamini kullan.
- Olumsuzluk, soru-bildirme yonu, sayisal deger, ozel ad ve teknik kimlik duzeltme sonrasinda da kaynak niyetle ayni kalmalidir."""
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GEMINI_FLASH_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_31_FLASH_LITE_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_CEREBRAS_MODEL = "llama3.1-8b"
DEFAULT_MISTRAL_MODEL = "open-mistral-nemo-2407"
DEFAULT_TIMING_REPAIR_API_TIMEOUT_SECONDS = 45
DEFAULT_GEMINI_FLASH_REQUEST_SPACING_SECONDS = 2.0
DEFAULT_GEMINI_31_FLASH_LITE_REQUEST_SPACING_SECONDS = 0.75
GEMINI_31_FLASH_LITE_HIGH_DEMAND_RETRY_DELAYS = (0.5, 1.0, 2.0, 4.0, 8.0)


class BridgeError(RuntimeError):
    def __init__(
        self,
        message: str,
        error_type: str = "bridge_error",
        retry_after_at: str = "",
        retry_after_seconds: int = 0,
        retry_reason: str = "",
        retryable: bool = False,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.retry_after_at = retry_after_at
        self.retry_after_seconds = retry_after_seconds
        self.retry_reason = retry_reason
        self.retryable = bool(retryable)


# API sağlayıcı uçları: yalnız https ve yalnız bu alan adları (file:, http:, başka host reddedilir).
IZINLI_API_ALAN_ADLARI = frozenset({
    "api.groq.com",
    "api.cerebras.ai",
    "api.mistral.ai",
    "generativelanguage.googleapis.com",
})


def api_url_dogrula(url: str) -> str:
    """Yalnız https şeması ve izinli sağlayıcı alan adı; kullanıcı:parola@ ve başka şema reddedilir."""
    parca = urllib.parse.urlsplit(url)
    if (
        parca.scheme != "https"
        or parca.username
        or parca.password
        or parca.hostname not in IZINLI_API_ALAN_ADLARI
    ):
        raise BridgeError(f"izinli olmayan API adresi: {parca.scheme}://{parca.hostname}", error_type="api_url_rejected")
    return url


class _YalnizHttpsYonlendirme(urllib.request.HTTPRedirectHandler):
    """Yönlendirme yalnız https'e; http/file'a düşüş reddedilir (anahtar başlığı açık metne gitmesin)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise urllib.error.HTTPError(newurl, code, "https olmayan yönlendirme reddedildi", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_API_ACICI = urllib.request.build_opener(_YalnizHttpsYonlendirme)


def _retry_after_from_usage_limit(text: str) -> tuple[str, int]:
    match = re.search(r"try again at\s+([0-9]{1,2})(?::([0-9]{2}))?\s*([AP]M)", text or "", re.IGNORECASE)
    if not match:
        retry_at = datetime.now() + timedelta(hours=1)
        return retry_at.isoformat(timespec="seconds"), 3600
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    am_pm = match.group(3).upper()
    if am_pm == "PM" and hour != 12:
        hour += 12
    if am_pm == "AM" and hour == 12:
        hour = 0
    now = datetime.now()
    retry_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if retry_at <= now:
        retry_at += timedelta(days=1)
    seconds = max(60, int((retry_at - now).total_seconds()))
    return retry_at.isoformat(timespec="seconds"), seconds


def classify_codex_cli_error(stderr: str, stdout: str = "") -> dict[str, Any]:
    combined = f"{stderr or ''}\n{stdout or ''}"
    lowered = combined.lower()
    if "you've hit your usage limit" in lowered or "you have hit your usage limit" in lowered or "usage limit" in lowered:
        retry_after_at, retry_after_seconds = _retry_after_from_usage_limit(combined)
        return {
            "error_type": "codex_usage_limit",
            "retryable": True,
            "retry_after_at": retry_after_at,
            "retry_after_seconds": retry_after_seconds,
            "retry_reason": "usage_limit",
        }
    if "reason: content_filter" in lowered:
        retry_after_at = (datetime.now() + timedelta(seconds=30)).isoformat(timespec="seconds")
        return {
            "error_type": "codex_content_filter",
            "retryable": True,
            "retry_after_at": retry_after_at,
            "retry_after_seconds": 30,
            "retry_reason": "content_filter",
        }
    if "failed to connect to websocket" in lowered or "stream disconnected before completion" in lowered or "connection" in lowered:
        retry_after_at = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
        return {
            "error_type": "codex_temporary_network",
            "retryable": True,
            "retry_after_at": retry_after_at,
            "retry_after_seconds": 600,
            "retry_reason": "temporary_network",
        }
    if "image_generation_user_error" in lowered or "gpt-image-2" in lowered:
        return {
            "error_type": "codex_cli_tool_config_error",
            "retryable": False,
            "retry_after_at": "",
            "retry_after_seconds": 0,
            "retry_reason": "tool_config",
        }
    return {
        "error_type": "codex_cli_error",
        "retryable": False,
        "retry_after_at": "",
        "retry_after_seconds": 0,
        "retry_reason": "unknown",
    }


def format_bridge_error(message: str, details: dict[str, Any]) -> str:
    payload = {"message": message, **details}
    return "CODEX_BRIDGE_ERROR " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for path in [INBOX_DIR, PROCESSING_DIR, OUTBOX_DIR, FAILED_DIR, LOGS_DIR, TMP_DIR, USAGE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": now_iso(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def estimate_text_tokens(text: str) -> int:
    return max(0, int(round(len(text or "") / 4)))


def usage_headers(headers: Any) -> dict[str, str]:
    if not headers:
        return {}
    tracked = {}
    for key in (
        "retry-after",
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-limit-requests-day",
        "x-ratelimit-remaining-requests-day",
        "x-ratelimit-reset-requests-day",
        "x-ratelimit-limit-tokens-minute",
        "x-ratelimit-remaining-tokens-minute",
        "x-ratelimit-reset-tokens-minute",
    ):
        value = headers.get(key) if hasattr(headers, "get") else None
        if value is not None:
            tracked[key] = str(value)
    return tracked


def record_api_usage(event: dict[str, Any]) -> None:
    safe_event = {
        "schema_version": 1,
        **event,
    }
    append_jsonl(API_USAGE_EVENTS_FILE, safe_event)
    update_api_usage_summary(safe_event)


def update_api_usage_summary(event: dict[str, Any]) -> None:
    day = str(event.get("timestamp") or now_iso())[:10]
    provider = str(event.get("provider") or "unknown")
    backend = str(event.get("backend") or "unknown")
    model = str(event.get("model") or "unknown")
    key = f"{day}|{provider}|{backend}|{model}"
    try:
        summary = read_json(API_USAGE_SUMMARY_FILE) if API_USAGE_SUMMARY_FILE.exists() else {}
    except Exception:
        summary = {}
    summary.setdefault("schema_version", 1)
    summary.setdefault("updated_at", now_iso())
    summary.setdefault("totals", {})
    bucket = summary["totals"].setdefault(key, {
        "day": day,
        "provider": provider,
        "backend": backend,
        "model": model,
        "request_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "estimated_input_tokens": 0,
        "last_status": "",
        "last_error_type": "",
        "last_updated_at": "",
    })
    bucket["request_count"] = int(bucket.get("request_count") or 0) + 1
    if event.get("status") == "success":
        bucket["success_count"] = int(bucket.get("success_count") or 0) + 1
    else:
        bucket["failed_count"] = int(bucket.get("failed_count") or 0) + 1
    for name in (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
        "estimated_input_tokens",
    ):
        bucket[name] = int(bucket.get(name) or 0) + int(event.get(name) or 0)
    bucket["last_status"] = str(event.get("status") or "")
    bucket["last_error_type"] = str(event.get("error_type") or "")
    bucket["last_updated_at"] = str(event.get("timestamp") or now_iso())
    summary["updated_at"] = now_iso()
    write_json(API_USAGE_SUMMARY_FILE, summary)


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)


def validate_job(job: dict[str, Any]) -> None:
    if not isinstance(job, dict):
        raise BridgeError("Job JSON object olmali")
    if job.get("task_type") == "full_text_translation":
        if not str(job.get("job_id") or "").strip():
            raise BridgeError("job_id bos olamaz")
        if not str(job.get("source_lang") or "").strip():
            raise BridgeError("source_lang bos olamaz")
        if not str(job.get("target_lang") or "").strip():
            raise BridgeError("target_lang bos olamaz")
        if not str(job.get("source_text") or "").strip():
            raise BridgeError("source_text bos olamaz")
        return
    if job.get("task_type") != "translation_candidates":
        raise BridgeError("Sadece task_type=translation_candidates destekleniyor")
    if not str(job.get("job_id") or "").strip():
        raise BridgeError("job_id bos olamaz")
    segments = job.get("segments")
    if not isinstance(segments, list) or not segments:
        raise BridgeError("segments bos olamaz")
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise BridgeError(f"segments[{index}] object olmali")
        if "id" not in segment:
            raise BridgeError(f"segments[{index}].id eksik")
        if not str(segment.get("text") or "").strip():
            raise BridgeError(f"segments[{index}].text bos olamaz")


def candidate_count(job: dict[str, Any]) -> int:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    count = int(options.get("candidate_count") or DEFAULT_CANDIDATE_COUNT)
    return max(1, min(count, MAX_ACCEPTED_CANDIDATES))


def normalized_candidate_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().strip(" .,!?:;"))


def normalize_result_candidates(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    expected_count = candidate_count(job)
    normalizations = []
    translations = result.get("translations")
    if not isinstance(translations, list):
        return normalizations
    for item in translations:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list):
            continue
        cleaned = [str(candidate).strip() for candidate in candidates if isinstance(candidate, str) and str(candidate).strip()]
        original_count = len(candidates)
        cleaned_count = len(cleaned)
        deduped = []
        seen_keys = set()
        duplicate_count = 0
        for candidate in cleaned:
            key = normalized_candidate_key(candidate)
            if key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(key)
            deduped.append(candidate)
        cleaned = deduped
        deduped_count = len(cleaned)
        options = job.get("options") if isinstance(job.get("options"), dict) else {}
        max_candidate_count = expected_count if options.get("mode") == "timing_repair" else MAX_ACCEPTED_CANDIDATES
        if len(cleaned) > max_candidate_count:
            cleaned = cleaned[:max_candidate_count]
        item["candidates"] = cleaned
        final_count = len(cleaned)
        if (
            original_count != final_count
            or final_count > expected_count
            or cleaned_count != original_count
            or duplicate_count > 0
        ):
            normalizations.append({
                "id": str(item.get("id")),
                "original_candidate_count": original_count,
                "nonempty_candidate_count": cleaned_count,
                "deduped_candidate_count": deduped_count,
                "final_candidate_count": final_count,
                "expected_candidate_count": expected_count,
                "max_accepted_candidate_count": max_candidate_count,
                "removed_duplicate_candidate_count": duplicate_count,
                "trimmed_candidate_count": max(0, deduped_count - final_count),
            })
    return normalizations


def normalize_gemini_kept_terms(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    segment_text_by_id = {
        str(segment.get("id")): str(segment.get("text") or "")
        for segment in job.get("segments", [])
        if isinstance(segment, dict)
    }
    allowed_reason_markers = (
        "brand",
        "organization",
        "organisation",
        "product",
        "person",
        "company",
        "model",
        "acronym",
        "abbreviation",
        "url",
        "domain",
        "proper",
        "protected",
    )
    normalizations = []
    for item in result.get("translations", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id"))
        source_text = segment_text_by_id.get(segment_id, "")
        kept_terms = item.get("kept_terms")
        if not isinstance(kept_terms, list):
            item["kept_terms"] = []
            normalizations.append({"id": segment_id, "reason": "kept_terms_not_list"})
            continue
        filtered = []
        removed = []
        for term in kept_terms:
            if not isinstance(term, dict):
                removed.append({"term": str(term), "reason": "not_object"})
                continue
            text = str(term.get("text") or "").strip()
            reason = str(term.get("reason") or "").strip().lower()
            if not text:
                removed.append({"term": text, "reason": "empty_text"})
                continue
            if text.lower() not in source_text.lower():
                removed.append({"term": text, "reason": "not_in_segment_source"})
                continue
            if not any(marker in reason for marker in allowed_reason_markers):
                removed.append({"term": text, "reason": "not_protected_term_reason", "source_reason": reason})
                continue
            filtered.append(term)
        if removed:
            item["kept_terms"] = filtered
            normalizations.append({"id": segment_id, "removed": removed})
    return normalizations


def normalize_kept_terms_to_spoken_candidates(result: dict[str, Any], job: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    segment_text_by_id = {}
    if isinstance(job, dict):
        segment_text_by_id = {
            str(segment.get("id")): str(segment.get("text") or "").lower()
            for segment in job.get("segments", [])
            if isinstance(segment, dict)
        }
    normalizations = []
    for item in result.get("translations", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id"))
        kept_terms = item.get("kept_terms")
        candidates = item.get("candidates")
        if not isinstance(kept_terms, list) or not isinstance(candidates, list):
            continue
        candidate_text = "\n".join(str(candidate or "") for candidate in candidates).lower()
        source_text = segment_text_by_id.get(segment_id, "")
        filtered = []
        removed = []
        for term in kept_terms:
            if not isinstance(term, dict):
                filtered.append(term)
                continue
            text = str(term.get("text") or "").strip()
            if text and text.lower() not in candidate_text:
                removed.append({"term": text, "reason": "not_spoken_in_candidates"})
                continue
            if text and source_text and text.lower() not in source_text:
                removed.append({"term": text, "reason": "not_in_segment_source"})
                continue
            filtered.append(term)
        if removed:
            item["kept_terms"] = filtered
            normalizations.append({"id": segment_id, "removed": removed})
    return normalizations


def normalize_gemini_fragment_candidates(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    segment_text_by_id = {
        str(segment.get("id")): str(segment.get("text") or "").strip().lower()
        for segment in job.get("segments", [])
        if isinstance(segment, dict)
    }
    normalizations = []
    for item in result.get("translations", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id"))
        source_text = segment_text_by_id.get(segment_id, "")
        candidates = item.get("candidates")
        if not isinstance(candidates, list):
            continue
        cleaned = [str(candidate).strip() for candidate in candidates if isinstance(candidate, str) and str(candidate).strip()]
        if not cleaned:
            continue
        kept = []
        removed = []
        for candidate in cleaned:
            lowered = candidate.lower()
            reason = ""
            if source_text == "sam altman's":
                if "altman" in lowered and ("ınki" in lowered or "inki" in lowered or "tarafından" in lowered):
                    reason = "possessive_fragment_drift"
            elif source_text == "openai api.":
                if "kullan" in lowered or "tarafından" in lowered:
                    reason = "object_fragment_added_verb"
            elif source_text == "rip.":
                if "rahmet" in lowered or "öld" in lowered or "oldu" in lowered or "vefat" in lowered:
                    reason = "reaction_fragment_death_drift"
            elif source_text == "mind map.":
                if lowered.strip(". ") in {"harita", "akıl haritası"}:
                    reason = "term_undertranslated"
            if reason:
                removed.append({"candidate": candidate, "reason": reason})
                continue
            kept.append(candidate)
        if removed and kept:
            item["candidates"] = kept
            normalizations.append({
                "id": segment_id,
                "source_text": source_text,
                "original_candidate_count": len(cleaned),
                "final_candidate_count": len(kept),
                "removed": removed,
            })
    return normalizations


def lowercase_clause_after_question_mark(value: Any) -> list[str]:
    text = str(value or "")
    violations = []
    for match in re.finditer(r"\?\s+([^\W\d_])", text, flags=re.UNICODE):
        next_character = match.group(1)
        if not next_character.islower():
            continue
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 32)
        excerpt = " ".join(text[start:end].split())
        violations.append(f"Soru isaretinden sonra kucuk harfle suren supheli cumle: {excerpt}")
    return violations


def full_text_source_review_warnings(job: dict[str, Any]) -> list[str]:
    if job.get("task_type") != "full_text_translation":
        return []
    return lowercase_clause_after_question_mark(job.get("source_text"))


def full_text_target_review_violations(result: dict[str, Any]) -> list[str]:
    if result.get("status") != "success":
        return []
    return lowercase_clause_after_question_mark(result.get("translated_text"))


def full_text_retry_violations(job: dict[str, Any]) -> list[str]:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    values = options.get("full_text_review_violations")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def build_full_text_review_retry_job(job: dict[str, Any], review_violations: list[str]) -> dict[str, Any]:
    retry_job = json.loads(json.dumps(job, ensure_ascii=False))
    options = retry_job.get("options") if isinstance(retry_job.get("options"), dict) else {}
    retry_job["options"] = {
        **options,
        "full_text_review_violations": review_violations,
    }
    return retry_job


def validate_result(job: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("job_id") != job.get("job_id"):
        raise BridgeError("Result job_id job ile eslesmiyor")
    result.pop("engine", None)
    if result.get("status") not in {"success", "partial", "failed"}:
        raise BridgeError("Result status gecersiz")
    injection_violations = cikti_enjeksiyon_ihlalleri(job, result)
    if injection_violations:
        raise BridgeError(
            "Ceviri ciktisi kaynakta olmayan icerik iceriyor (olasi istem enjeksiyonu): "
            + "; ".join(injection_violations[:5]),
            error_type="translation_result_injection_suspected",
            retry_reason="unexpected_link_or_meta_line",
            retryable=True,
        )
    if job.get("task_type") == "full_text_translation":
        translated_text = result.get("translated_text")
        if result.get("status") == "success" and (not isinstance(translated_text, str) or not translated_text.strip()):
            raise BridgeError("Full metin success result translated_text icermeli")
        if result.get("status") == "success":
            integrity = result.get("integrity")
            if not isinstance(integrity, dict):
                raise BridgeError("Full metin success result integrity icermeli")
            if integrity.get("source_coverage") != "complete":
                raise BridgeError("Full metin success result tam kaynak kapsami beyan etmeli")
            if integrity.get("omitted_source_content") or integrity.get("added_content"):
                raise BridgeError("Full metin success result eksiltme veya ekleme beyan ediyor")
            review_violations = full_text_target_review_violations(result)
            if review_violations:
                raise BridgeError(
                    "Full metin cevirisi supheli cumle siniri iceriyor: "
                    + "; ".join(review_violations)
                )
        return
    translations = result.get("translations")
    if not isinstance(translations, list):
        raise BridgeError("Result translations liste olmali")

    expected_ids = [segment["id"] for segment in job["segments"]]
    expected_set = {str(item) for item in expected_ids}
    seen_ids = [str(item.get("id")) for item in translations if isinstance(item, dict)]
    seen_set = set(seen_ids)
    missing = expected_set - seen_set
    if missing and minimal_translation_result_job(job):
        raise BridgeError(
            f"Result eksik segment iceriyor: {sorted(missing)}",
            error_type="translation_result_incomplete",
            retry_reason="missing_segment_ids",
            retryable=True,
        )
    if missing and result.get("status") == "success":
        raise BridgeError(f"Success result eksik segment iceriyor: {sorted(missing)}")
    if gemini_strict_segment_contract_enabled() and result.get("status") == "success":
        duplicate_ids = sorted({item for item in seen_ids if seen_ids.count(item) > 1})
        if duplicate_ids:
            raise BridgeError(f"Gemini strict result duplicate segment iceriyor: {duplicate_ids}")
        extra_ids = sorted(seen_set - expected_set)
        if extra_ids:
            raise BridgeError(f"Gemini strict result fazla segment iceriyor: {extra_ids}")

    for item in translations:
        if not isinstance(item, dict):
            raise BridgeError("Translation item object olmali")
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            if minimal_translation_result_job(job):
                raise BridgeError(
                    f"Segment {item.get('id')} candidates bos",
                    error_type="translation_result_incomplete",
                    retry_reason="empty_candidates",
                    retryable=True,
                )
            raise BridgeError(f"Segment {item.get('id')} candidates bos")
        if len(candidates) > MAX_ACCEPTED_CANDIDATES:
            raise BridgeError(f"Segment {item.get('id')} aday sayisi {len(candidates)}, ust sinir {MAX_ACCEPTED_CANDIDATES}")
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                if minimal_translation_result_job(job):
                    raise BridgeError(
                        f"Segment {item.get('id')} bos aday iceriyor",
                        error_type="translation_result_incomplete",
                        retry_reason="empty_candidate_text",
                        retryable=True,
                    )
                raise BridgeError(f"Segment {item.get('id')} bos aday iceriyor")
        if not minimal_translation_result_job(job):
            if "kept_terms" not in item:
                raise BridgeError(f"Segment {item.get('id')} kept_terms alani zorunlu")
            kept_terms = item.get("kept_terms")
            if not isinstance(kept_terms, list):
                raise BridgeError(f"Segment {item.get('id')} kept_terms liste olmali")
            for term in kept_terms:
                if not isinstance(term, dict):
                    raise BridgeError(f"Segment {item.get('id')} kept_terms item object olmali")
                if not str(term.get("text") or "").strip():
                    raise BridgeError(f"Segment {item.get('id')} kept_terms text bos")
                if not str(term.get("reason") or "").strip():
                    raise BridgeError(f"Segment {item.get('id')} kept_terms reason bos")
                confidence = term.get("confidence")
                if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                    raise BridgeError(f"Segment {item.get('id')} kept_terms confidence 0-1 olmali")

    if is_natural_blocks_job(job):
        quality_review_violations = natural_blocks_review_violations(job, result)
        if quality_review_violations:
            failed_ids = sorted({
                segment_id
                for violation in quality_review_violations
                for segment_id in violation.get("failed_segment_ids", [])
            })
            raise BridgeError(
                f"Natural Blocks grup kalite kontrolu basarisiz: {failed_ids}",
                error_type="translation_result_quality_failed",
                retry_reason="natural_blocks_chain_review_failed",
                retryable=True,
            )


def validate_output_language(job: dict[str, Any], result: dict[str, Any]) -> None:
    """Aday metinleri hedef dilde mi (hedef_dil.cikti_dili_ihlalleri); degilse yeniden denenebilir acik hata (ADR 0009, 0014)."""
    violations = hedef_dil.cikti_dili_ihlalleri(job, result)
    if violations:
        raise BridgeError(
            "Ceviri ciktisi hedef dilde degil ("
            + hedef_dil.is_hedef_dili(job)
            + "): "
            + "; ".join(violations[:5]),
            error_type="translation_result_wrong_language",
            retry_reason="output_language_mismatch",
            retryable=True,
        )


def expected_segment_ids(job: dict[str, Any]) -> list[str]:
    return [str(segment.get("id")) for segment in job.get("segments", []) if isinstance(segment, dict)]


def seen_translation_ids(result: dict[str, Any]) -> set[str]:
    return {str(item.get("id")) for item in result.get("translations", []) if isinstance(item, dict)}


def missing_segment_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    seen = seen_translation_ids(result)
    return [
        {
            "id": segment_id,
            "kind": "missing_segment",
            "message": "Model success sonucunda bu segment id'sini dondurmedi.",
        }
        for segment_id in expected_segment_ids(job)
        if segment_id not in seen
    ]


def is_timing_repair_job(job: dict[str, Any]) -> bool:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    mode = str(options.get("mode") or "").strip().lower()
    return mode == "timing_repair"


def timing_repair_api_timeout_seconds(job: dict[str, Any], timeout_seconds: int) -> int:
    if not is_timing_repair_job(job):
        return int(timeout_seconds)
    raw_value = os.getenv("CODEX_BRIDGE_TIMING_REPAIR_API_TIMEOUT_SECONDS", "").strip()
    try:
        configured = int(raw_value) if raw_value else DEFAULT_TIMING_REPAIR_API_TIMEOUT_SECONDS
    except ValueError:
        configured = DEFAULT_TIMING_REPAIR_API_TIMEOUT_SECONDS
    configured = max(10, configured)
    return min(int(timeout_seconds), configured)


def candidate_word_count(value: str, target_lang: str = "") -> int:
    def sayac(metin: str) -> int:
        return len(re.findall(r"\b[\w'’]+\b", metin or "", re.UNICODE))

    return hedef_dil.kelime_esdegeri(value, target_lang or "tr", sayac)


def segment_contract_minimum(segment: dict[str, Any]) -> int:
    for key in ("invalid_if_below_word_count", "hard_minimum_word_count"):
        try:
            value = int(segment.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def timing_contract_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    segments = {str(segment.get("id")): segment for segment in job.get("segments", []) if isinstance(segment, dict)}
    violations = []
    for item in result.get("translations", []):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id"))
        segment = segments.get(segment_id)
        if not segment:
            continue
        minimum = segment_contract_minimum(segment)
        if minimum <= 0:
            continue
        candidate_details = []
        valid_candidate_count = 0
        for index, candidate in enumerate(item.get("candidates", [])):
            count = candidate_word_count(candidate, hedef_dil.is_hedef_dili(job))
            if count < minimum:
                candidate_details.append({
                    "candidate_index": index,
                    "word_count": count,
                    "minimum_word_count": minimum,
                    "text": str(candidate)[:240],
                })
            else:
                valid_candidate_count += 1
        if candidate_details and valid_candidate_count == 0:
            violations.append({
                "id": segment_id,
                "minimum_word_count": minimum,
                "candidate_count": len(item.get("candidates", [])),
                "valid_candidate_count": valid_candidate_count,
                "violating_candidates": candidate_details,
            })
    return violations


def candidate_count_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    expected_count = candidate_count(job)
    violations = []
    for item in result.get("translations", []):
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            continue
        actual_count = len(candidates)
        if actual_count < expected_count:
            violations.append({
                "id": str(item.get("id")),
                "kind": "candidate_count",
                "candidate_count": actual_count,
                "expected_candidate_count": expected_count,
                "missing_candidate_count": expected_count - actual_count,
                "existing_candidates": [str(candidate) for candidate in candidates if str(candidate).strip()],
            })
    return violations


def repair_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {}
    for violation in missing_segment_violations(job, result):
        segment_id = str(violation["id"])
        by_id[segment_id] = violation
    return list(by_id.values())


def build_contract_retry_job(job: dict[str, Any], result: dict[str, Any], violations: list[dict[str, Any]], attempt: int) -> dict[str, Any]:
    violation_ids = {str(item["id"]) for item in violations}
    previous = {str(item.get("id")): item.get("candidates", []) for item in result.get("translations", []) if isinstance(item, dict)}
    retry_job = json.loads(json.dumps(job, ensure_ascii=False))
    retry_job["job_id"] = f"{job['job_id']}_contract_retry_{attempt}"
    options = retry_job.get("options") if isinstance(retry_job.get("options"), dict) else {}
    options = dict(options)
    options["mode"] = "timing_contract_retry"
    options["contract_retry_attempt"] = attempt
    retry_job["options"] = options
    retry_segments = []
    for segment in retry_job.get("segments", []):
        segment_id = str(segment.get("id"))
        if segment_id not in violation_ids:
            continue
        copy_segment = dict(segment)
        copy_segment["previous_invalid_candidates"] = previous.get(segment_id, [])
        copy_segment["contract_retry"] = next(item for item in violations if str(item["id"]) == segment_id)
        retry_segments.append(copy_segment)
    retry_job["segments"] = retry_segments
    retry_job["contract_retry_instruction"] = (
        "Önceki cevap onarılabilir çeviri sözleşmesini ihlal etti. "
        "Sadece verilen segmentler için yeniden aday üret. "
        "Çıktıda yalnızca bu retry job içindeki segments id'leri bulunmalıdır. "
        "Context id'lerini veya önceki başarılı id'leri translations içine yazma. "
        "Verilen her segments id'si için tam bir translation item döndür; hiçbir id eksik kalamaz. "
        "Parçalı cümleyi başka id ile birleştirme; her id kendi kaynak parçasının çevirisini taşımalıdır. "
        "Her segment için mümkünse candidate_count kadar aday döndür. "
        "Kaynakta olmayan bilgi ekleme. Kelime sayısını doldurmak için doğal ve doğru bir adayı uzatma. "
        "Aynı kaynak anlamını, konuşmacının niyetini ve üslubunu koruyan doğal "
        + hedef_dil.dil_adi(hedef_dil.is_hedef_dili(job))
        + " dublaj repliği olarak kur."
    )
    return retry_job


def merge_retry_result(result: dict[str, Any], retry_result: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(result, ensure_ascii=False))
    replacements = {str(item.get("id")): item for item in retry_result.get("translations", []) if isinstance(item, dict)}
    current = {str(item.get("id")): item for item in merged.get("translations", []) if isinstance(item, dict)}
    translations = []
    used = set()
    for item in merged.get("translations", []):
        segment_id = str(item.get("id"))
        if segment_id in replacements:
            replacement_candidates = replacements[segment_id].get("candidates", [])
            current_candidates = current.get(segment_id, {}).get("candidates", [])
            if isinstance(replacement_candidates, list) and isinstance(current_candidates, list) and len(replacement_candidates) < len(current_candidates):
                translations.append(item)
            else:
                translations.append(replacements[segment_id])
            used.add(segment_id)
        else:
            translations.append(item)
    for segment_id, item in replacements.items():
        if segment_id not in used:
            translations.append(item)
    merged["translations"] = translations
    return merged


def run_natural_blocks_with_chain_review(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    result, meta = run_bridge_model(job, timeout_seconds)
    retry_meta = []
    for attempt in range(1, MAX_NATURAL_BLOCKS_CHAIN_REVIEW_RETRIES + 1):
        violations = natural_blocks_review_violations(job, result)
        if not violations:
            break
        retry_job = build_natural_blocks_review_retry_job(job, result, violations, attempt)
        retry_result, one_meta = run_bridge_model(retry_job, timeout_seconds)
        result = replace_natural_blocks_retry_result(job, result, retry_result)
        retry_meta.append({
            "attempt": attempt,
            "scope": "whole_translation_group",
            "violation_count": len(violations),
            "violations": violations,
            "failed_segment_ids": sorted({
                segment_id
                for violation in violations
                for segment_id in violation.get("failed_segment_ids", [])
            }),
            "meta": one_meta,
        })
    remaining = natural_blocks_review_violations(job, result)
    if not remaining and seen_translation_ids(result) == set(expected_segment_ids(job)):
        result["status"] = "success"
    meta["contract_retry"] = {
        "attempts": len(retry_meta),
        "mode": "natural_blocks_chain_review",
        "remaining_violation_count": len(remaining),
        "remaining_segment_ids": sorted({
            segment_id
            for violation in remaining
            for segment_id in violation.get("failed_segment_ids", [])
        }),
        "runs": retry_meta,
    }
    return result, meta


def run_codex_with_contract_retry(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if is_natural_blocks_job(job):
        return run_natural_blocks_with_chain_review(job, timeout_seconds)
    result, meta = run_bridge_model(job, timeout_seconds)
    if job.get("task_type") == "full_text_translation":
        retry_meta = []
        initial_status = str(result.get("status") or "")
        for attempt in range(1, MAX_FULL_TEXT_PARTIAL_RETRIES + 1):
            review_violations = full_text_target_review_violations(result)
            if result.get("status") != "partial" and not review_violations:
                break
            retry_job = build_full_text_review_retry_job(job, review_violations)
            previous_status = str(result.get("status") or "")
            result, one_meta = run_bridge_model(retry_job, timeout_seconds)
            retry_meta.append({
                "attempt": attempt,
                "previous_status": previous_status,
                "review_violations": review_violations,
                "returned_status": str(result.get("status") or ""),
                "meta": one_meta,
            })
        meta["contract_retry"] = {
            "attempts": len(retry_meta),
            "mode": "full_text_translation",
            "initial_status": initial_status,
            "final_status": str(result.get("status") or ""),
            "runs": retry_meta,
        }
        return result, meta
    job_id_retry_meta = []
    for attempt in range(1, MAX_JOB_ID_MISMATCH_RETRIES + 1):
        if result.get("job_id") == job.get("job_id"):
            break
        returned_job_id = str(result.get("job_id") or "")
        result, retry_meta = run_bridge_model(job, timeout_seconds)
        job_id_retry_meta.append({
            "attempt": attempt,
            "returned_job_id": returned_job_id,
            "meta": retry_meta,
        })
    meta["job_id_mismatch_retry"] = {
        "attempts": len(job_id_retry_meta),
        "matched": result.get("job_id") == job.get("job_id"),
        "runs": job_id_retry_meta,
    }
    retry_meta = []
    for attempt in range(1, MAX_CONTRACT_RETRIES + 1):
        violations = repair_violations(job, result)
        if not violations:
            break
        retry_job = build_contract_retry_job(job, result, violations, attempt)
        if not retry_job.get("segments"):
            break
        retry_result, one_meta = run_bridge_model(retry_job, timeout_seconds)
        result = merge_retry_result(result, retry_result)
        retry_meta.append({
            "attempt": attempt,
            "violation_count": len(violations),
            "segment_ids": [item["id"] for item in violations],
            "meta": one_meta,
        })
    remaining = repair_violations(job, result)
    timing_advisories = timing_contract_violations(job, result)
    remaining_candidate_count = candidate_count_violations(job, result)
    meta["contract_retry"] = {
        "attempts": len(retry_meta),
        "remaining_violation_count": len(remaining),
        "remaining_segment_ids": [item["id"] for item in remaining],
        "remaining_candidate_count_violation_count": len(remaining_candidate_count),
        "remaining_candidate_count_segment_ids": [item["id"] for item in remaining_candidate_count],
        "timing_advisory_violation_count": len(timing_advisories),
        "timing_advisory_segment_ids": [item["id"] for item in timing_advisories],
        "runs": retry_meta,
    }
    return result, meta


def acquire_job() -> Path | None:
    ensure_dirs()
    jobs = sorted(path for path in INBOX_DIR.glob("*.json") if path.is_file())
    if not jobs:
        return None
    source = jobs[0]
    target = PROCESSING_DIR / source.name
    source.replace(target)
    return target


def read_prompt_file(path: Path) -> str:
    prompt = path.read_text(encoding="utf-8")
    if "\x00" in prompt:
        raise BridgeError(f"Prompt dosyasi NUL byte iceriyor: {path}")
    if not prompt.strip():
        raise BridgeError(f"Prompt dosyasi bos: {path}")
    return prompt


def discourse_context_payload(job: dict[str, Any]) -> dict[str, Any]:
    main_job_segments = [segment for segment in job.get("segments", []) if isinstance(segment, dict)]
    main_segment_ids = [str(segment.get("id")) for segment in main_job_segments]
    main_segment_id_set = set(main_segment_ids)
    full_discourse_segments = [segment for segment in job.get("discourse_segments", []) if isinstance(segment, dict)]
    if full_discourse_segments:
        ordered_segments = []
        ordered_source_texts = []
        for segment in full_discourse_segments:
            source_text = str(segment.get("original_source_text") or segment.get("text") or "").strip()
            if not source_text:
                continue
            segment_id = str(segment.get("id"))
            ordered_source_texts.append(source_text)
            ordered_segments.append({
                "role": "main" if segment_id in main_segment_id_set else "discourse_context",
                "id": segment_id,
                "translation_required": segment_id in main_segment_id_set,
            })
        main_source_segments = []
        main_current_target_segments = []
        for segment in main_job_segments:
            source_text = str(segment.get("original_source_text") or segment.get("text") or "").strip()
            current_target_text = str(segment.get("text") or "").strip()
            if source_text:
                main_source_segments.append(source_text)
            if segment.get("original_source_text") and current_target_text:
                main_current_target_segments.append(current_target_text)
        return {
            "ordered_source_text": " ".join(ordered_source_texts),
            "main_source_text": " ".join(main_source_segments),
            "main_current_target_text": " ".join(main_current_target_segments),
            "main_segment_ids": main_segment_ids,
            "ordered_segments": ordered_segments,
            "priority": f"meaning_intent_register_natural_spoken_{hedef_dil.konusma_slug(hedef_dil.is_hedef_dili(job))}_before_timing",
        }

    ordered_segments = []
    for role, key in (
        ("context_before", "context_before"),
        ("main", "segments"),
        ("context_after", "context_after"),
    ):
        for segment in job.get(key, []):
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text") or "").strip()
            if not text:
                continue
            ordered_segments.append({
                "role": role,
                "id": str(segment.get("id")),
                "text": text,
                "translation_required": role == "main",
            })
    main_segments = [segment for segment in ordered_segments if segment["role"] == "main"]
    return {
        "ordered_source_text": " ".join(segment["text"] for segment in ordered_segments),
        "main_source_text": " ".join(segment["text"] for segment in main_segments),
        "main_current_target_text": "",
        "main_segment_ids": [segment["id"] for segment in main_segments],
        "ordered_segments": ordered_segments,
        "priority": f"meaning_intent_register_natural_spoken_{hedef_dil.konusma_slug(hedef_dil.is_hedef_dili(job))}_before_timing",
    }


def prompt_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    prompt_job = json.loads(json.dumps(
        {key: value for key, value in job.items() if not str(key).startswith("_")},
        ensure_ascii=False,
    ))
    prompt_job["discourse_context"] = discourse_context_payload(job)
    prompt_job.pop("discourse_segments", None)
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    prompt_mode = str(options.get("prompt_mode") or "").strip()
    model_hidden_timing_fields = {
        "hard_minimum_word_count",
        "invalid_if_below_word_count",
        "minimum_fill_word_count",
        "repair_minimum_word_count",
        "timing_contract",
        "too_short_below_words",
    }
    if prompt_mode in {"supertonic_single_pass_1_natural", "supertonic_natural_blocks_1"}:
        model_hidden_timing_fields.update({
        "candidate_word_count_targets",
        "duration",
        "duration_strategy",
        "end",
        "hedef_kelime",
        "kelime_aralik",
        "maximum_fill_word_count",
        "previous_max_word_count",
        "profile_required_word_range",
        "profile_target_word_count",
        "repair_recommended_word_range",
        "repair_target_word_count",
        "repair_word_count_strategy",
        "recommended_word_range",
        "raw_tts_target_duration",
        "source_word_count",
        "start",
        "target_word_count",
        "timing_acceptance",
        "timing_feasibility",
        })
    if prompt_mode == "supertonic_natural_blocks_1":
        model_hidden_timing_fields.update({"fragment_guidance", "meaning_safety_contract"})
    for segment in prompt_job.get("segments", []):
        if not isinstance(segment, dict):
            continue
        for field_name in model_hidden_timing_fields:
            segment.pop(field_name, None)
    return prompt_job


def build_prompt(job: dict[str, Any], prompt_file: Path | None = None) -> str:
    selected_prompt_file = prompt_file or backend_prompt_file(job)
    prompt = (
        hedef_dil.istem_isle(read_prompt_file(selected_prompt_file), hedef_dil.is_hedef_dili(job))
        + "\n\n"
        + ASR_CONTEXTUAL_CORRECTION_PROMPT
        + "\n\n"
        + VERI_TALIMAT_AYRIMI
    )
    prompt_job = prompt_job_payload(job)
    if job.get("task_type") == "full_text_translation":
        source_warnings = full_text_source_review_warnings(job)
        retry_violations = full_text_retry_violations(job)
        review_text = ""
        if source_warnings:
            review_text += (
                "\n\nOTOMATIK TRANSKRIPT DENETIM UYARISI:\n- "
                + "\n- ".join(source_warnings)
            )
        if retry_violations:
            review_text += (
                "\n\nONCEKI CEVIRI DENETIM IHLALLERI:\n- "
                + "\n- ".join(retry_violations)
                + "\nKaynak metinden yeni bir tam ceviri uret ve bu ihlalleri teslim etmeden once gider."
            )
        return prompt + review_text + "\n\nJOB JSON:\n" + json.dumps(prompt_job, ensure_ascii=False, indent=2)
    if gemini_strict_segment_contract_enabled():
        prompt_job["strict_segment_contract"] = gemini_strict_contract_payload(job)
    return (
        prompt
        + "\n\n"
        + "Aday sayısı: "
        + str(candidate_count(job))
        + "\n\n"
        + gemini_strict_prompt_suffix(job)
        + "\n\n"
        + "JOB JSON:\n"
        + json.dumps(prompt_job, ensure_ascii=False, indent=2)
    )


def codex_backend_config() -> dict[str, Any]:
    return read_json(CODEX_BACKEND_CONFIG_FILE)


def minimal_translation_result_job(job: dict[str, Any] | None = None) -> bool:
    options = job.get("options") if isinstance(job, dict) and isinstance(job.get("options"), dict) else {}
    return str(options.get("prompt_mode") or "").strip() in {
        "supertonic_natural_blocks_1",
        "supertonic_whole_chain_master",
        "supertonic_whole_chain_candidates",
        "supertonic_whole_chain_repair",
    }


def codex_output_schema_file(job: dict[str, Any] | None = None) -> Path:
    config = codex_backend_config()
    output_schemas = config.get("output_schemas") if isinstance(config.get("output_schemas"), dict) else {}
    options = job.get("options") if isinstance(job, dict) and isinstance(job.get("options"), dict) else {}
    prompt_mode = str(options.get("prompt_mode") or "").strip()
    value = str(
        output_schemas.get(prompt_mode)
        or output_schemas.get("default")
        or config.get("output_schema")
        or RESULT_SCHEMA.name
    ).strip()
    path = Path(value)
    if not path.is_absolute():
        path = CODEX_BACKEND_CONFIG_FILE.parent / path
    return path


def codex_output_schema_payload(job: dict[str, Any]) -> dict[str, Any]:
    schema = hedef_dil.sema_isle(read_json(codex_output_schema_file(job)), hedef_dil.is_hedef_dili(job))
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        raise BridgeError("job_id bos olamaz")
    schema["properties"]["job_id"] = {"type": "string", "enum": [job_id]}
    return schema


def write_codex_output_schema(job: dict[str, Any]) -> Path:
    job_id = safe_name(str(job["job_id"]))
    schema_path = TMP_DIR / f"{job_id}_output_schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(schema_path, codex_output_schema_payload(job))
    return schema_path


def codex_prompt_file(job: dict[str, Any] | None = None) -> Path:
    config = codex_backend_config()
    prompt_files = config.get("prompt_files") if isinstance(config.get("prompt_files"), dict) else {}
    voice = job.get("voice") if isinstance(job, dict) and isinstance(job.get("voice"), dict) else {}
    options = job.get("options") if isinstance(job, dict) and isinstance(job.get("options"), dict) else {}
    engine = str(voice.get("engine") or "").strip()
    prompt_mode = str(options.get("prompt_mode") or "").strip()
    key = prompt_mode if prompt_mode in prompt_files else engine if engine in prompt_files else "default"
    value = str(prompt_files.get(key) or prompt_files.get("default") or "prompt.md").strip()
    path = Path(value)
    if not path.is_absolute():
        path = CODEX_BACKEND_CONFIG_FILE.parent / path
    return path


def backend_prompt_file(job: dict[str, Any] | None = None) -> Path:
    backend = bridge_backend()
    if backend == "gemini_31_flash_lite":
        value = os.getenv("CODEX_BRIDGE_GEMINI_31_FLASH_LITE_PROMPT_FILE", "").strip()
        if value:
            return Path(value)
        return DEFAULT_GEMINI_31_FLASH_LITE_PROMPT_FILE
    if backend == "gemini_flash":
        value = os.getenv("CODEX_BRIDGE_GEMINI_PROMPT_FILE", "").strip()
        if value:
            return Path(value)
        return DEFAULT_GEMINI_PROMPT_FILE
    if backend == "gemma":
        return BRIDGE_ROOT / "backends" / "gemma_4_26b" / "prompt.md"
    if backend == "groq":
        return BRIDGE_ROOT / "backends" / "groq_llama_4_scout" / "prompt.md"
    if backend == "cerebras":
        return BRIDGE_ROOT / "backends" / "cerebras_llama_3_1_8b" / "prompt.md"
    if backend == "mistral":
        return BRIDGE_ROOT / "backends" / "mistral_nemo" / "prompt.md"
    return codex_prompt_file(job)


def gemini_prompt_file() -> Path:
    backend = bridge_backend()
    if backend in {"gemini_flash", "gemini_31_flash_lite", "gemma"}:
        return backend_prompt_file()
    value = os.getenv("CODEX_BRIDGE_GEMINI_PROMPT_FILE", "").strip()
    if value:
        return Path(value)
    return DEFAULT_GEMINI_PROMPT_FILE


def gemini_strict_segment_contract_enabled() -> bool:
    if bridge_backend() != "gemini_31_flash_lite":
        return False
    value = os.getenv("CODEX_BRIDGE_GEMINI_STRICT_SEGMENT_CONTRACT", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def gemini_strict_temperature(job: dict[str, Any]) -> float:
    env_name = "CODEX_BRIDGE_GEMINI_STRICT_RETRY_TEMPERATURE" if is_contract_retry_job(job) else "CODEX_BRIDGE_GEMINI_STRICT_TEMPERATURE"
    default_value = "0.05" if is_contract_retry_job(job) else "0.15"
    try:
        return float(os.getenv(env_name, default_value).strip() or default_value)
    except ValueError:
        return float(default_value)


def gemini_temperature(job: dict[str, Any]) -> float:
    if gemini_strict_segment_contract_enabled():
        return gemini_strict_temperature(job)
    return float(os.getenv("CODEX_BRIDGE_GEMINI_TEMPERATURE", "0.35"))


def is_contract_retry_job(job: dict[str, Any]) -> bool:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    return str(options.get("mode") or "").strip().lower() == "timing_contract_retry"


def gemini_strict_contract_payload(job: dict[str, Any]) -> dict[str, Any]:
    main_ids = expected_segment_ids(job)
    before_ids = [str(segment.get("id")) for segment in job.get("context_before", []) if isinstance(segment, dict)]
    after_ids = [str(segment.get("id")) for segment in job.get("context_after", []) if isinstance(segment, dict)]
    return {
        "mode": "gemini_31_flash_lite_strict_segment_contract",
        "required_translation_ids": main_ids,
        "required_translation_count": len(main_ids),
        "readonly_context_ids": before_ids + after_ids,
        "forbidden_translation_ids": before_ids + after_ids,
        "candidate_count": candidate_count(job),
        "rules": [
            "translations must contain exactly required_translation_count items",
            "each required_translation_ids value must appear exactly once",
            "readonly context ids must never appear in translations",
            "do not merge multiple segment ids into one translation item",
            "do not move meaning from one id to another id",
            "status success is invalid if any required id is missing",
        ],
    }


def gemini_strict_prompt_suffix(job: dict[str, Any]) -> str:
    if not gemini_strict_segment_contract_enabled():
        return ""
    contract = gemini_strict_contract_payload(job)
    return (
        "GEMINI STRICT SEGMENT CONTRACT:\n"
        "- Bu istek gemini-3.1-flash-lite için timeline kilitli dublaj çevirisidir.\n"
        "- Çevrilecek tek liste JOB JSON içindeki segments listesidir.\n"
        "- context_before ve context_after yalnızca okunacak bağlamdır; bu id'leri translations içine yazmak yasaktır.\n"
        "- translations içinde şu id'ler tam olarak birer kez bulunmalıdır: "
        + ", ".join(contract["required_translation_ids"])
        + "\n"
        "- translations sayısı tam olarak "
        + str(contract["required_translation_count"])
        + " olmalıdır.\n"
        "- Kısa veya parçalı segmentleri birleştirme; her id kendi kaynak parçasının çevirisini taşır.\n"
        "- Eksik id, fazla id, duplicate id, context id veya id-anlam kayması varsa status success döndürme."
    )


def gemini_result_response_json_schema(job: dict[str, Any]) -> dict[str, Any]:
    ids = expected_segment_ids(job)
    return {
        "type": "object",
        "required": ["job_id", "status", "notes", "translations"],
        "properties": {
            "job_id": {"type": "string"},
            "status": {"type": "string", "enum": ["success", "partial", "failed"]},
            "notes": {"type": "string"},
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "candidates", "kept_terms"],
                    "properties": {
                        "id": {"type": "string", "enum": ids},
                        "candidates": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "kept_terms": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["text", "reason", "confidence"],
                                "properties": {
                                    "text": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder()
    parsed_objects = []
    for match in re.finditer(r"\{", stripped):
        try:
            parsed, _ = decoder.raw_decode(stripped[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parsed_objects.append(parsed)
    for parsed in reversed(parsed_objects):
        if isinstance(parsed.get("translations"), list) or parsed.get("status") == "success":
            return parsed
    if parsed_objects:
        return parsed_objects[-1]
    raise BridgeError("Codex final cevabinda JSON bulunamadi")


def extract_session_id(text: str) -> str:
    match = re.search(r"session id:\s*([0-9a-fA-F-]{36})", text or "")
    if not match:
        return ""
    return match.group(1)


def find_codex_session_file(session_id: str) -> Path | None:
    if not session_id or not CODEX_SESSION_ROOT.exists():
        return None
    matches = list(CODEX_SESSION_ROOT.rglob(f"*{session_id}*.jsonl"))
    if len(matches) != 1:
        return None
    return matches[0]


def cleanup_codex_session(session_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "session_id": session_id,
        "status": "",
        "deleted": False,
        "path": "",
        "error": "",
    }
    if not session_id:
        result["status"] = "missing_id"
        result["error"] = "session_id bulunamadi"
        return result

    session_file = None
    for _ in range(10):
        matches = list(CODEX_SESSION_ROOT.rglob(f"*{session_id}*.jsonl"))
        if len(matches) == 1:
            session_file = matches[0]
            break
        if len(matches) > 1:
            result["status"] = "ambiguous"
            result["error"] = "birden fazla session dosyasi eslesti"
            return result
        time.sleep(0.2)
    if session_file is None:
        result["status"] = "already_absent"
        return result

    try:
        resolved_root = CODEX_SESSION_ROOT.resolve()
        resolved_file = session_file.resolve()
        if resolved_root not in resolved_file.parents:
            result["status"] = "unsafe_path"
            result["error"] = "session dosyasi guvenli kok disinda"
            return result
        result["path"] = str(resolved_file)
        resolved_file.unlink()
        result["status"] = "deleted"
        result["deleted"] = True
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result


def run_mock(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("task_type") == "full_text_translation":
        return {
            "job_id": job["job_id"],
            "status": "success",
            "translated_text": str(job["source_text"]).strip(),
            "integrity": {
                "source_coverage": "complete",
                "omitted_source_content": [],
                "added_content": [],
            },
        }
    count = candidate_count(job)
    translations = []
    for segment in job["segments"]:
        source = str(segment["text"]).strip()
        base = f"Bu segment icin dogal {hedef_dil.dil_adi_ascii(hedef_dil.is_hedef_dili(job))} dublaj adayi"
        candidates = [f"{base} {idx + 1}: {source}" for idx in range(count)]
        translations.append({"id": segment["id"], "candidates": candidates, "kept_terms": []})
    return {
        "job_id": job["job_id"],
        "status": "success",
        "notes": "Mock modunda uretildi; gercek ceviri degildir.",
        "translations": translations,
    }


def codex_model() -> str:
    model = os.getenv("CODEX_BRIDGE_CODEX_MODEL", DEFAULT_CODEX_MODEL).strip()
    return model or DEFAULT_CODEX_MODEL


def full_text_source_word_count(job: dict[str, Any] | None) -> int:
    if not isinstance(job, dict) or job.get("task_type") != "full_text_translation":
        return 0
    return len(str(job.get("source_text") or "").split())


def codex_reasoning_effort(job: dict[str, Any] | None = None) -> str:
    if full_text_source_word_count(job) > FULL_TEXT_HIGH_REASONING_WORD_THRESHOLD:
        return "high"
    effort = os.getenv("CODEX_BRIDGE_CODEX_REASONING_EFFORT", DEFAULT_CODEX_REASONING_EFFORT).strip().lower()
    return effort if effort in VALID_CODEX_REASONING_EFFORTS else DEFAULT_CODEX_REASONING_EFFORT


def codex_command_prefix() -> list[str]:
    """Codex CLI komutu: CODEX_BRIDGE_CODEX_BIN, yoksa PATH'teki codex (Windows'ta .cmd kabugu icin cmd /c)."""
    explicit = os.getenv("CODEX_BRIDGE_CODEX_BIN", "").strip()
    resolved = explicit if explicit and Path(explicit).is_file() else shutil.which("codex")
    if not resolved:
        return ["cmd", "/c", "codex"] if os.name == "nt" else ["codex"]
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", resolved]
    return [resolved]


def build_codex_command(
    last_message_file: Path,
    output_schema_file: Path = RESULT_SCHEMA,
    job: dict[str, Any] | None = None,
) -> list[str]:
    work_dir = codex_exec_work_dir()
    disabled_feature_args = [
        argument
        for feature in CODEX_EXEC_DISABLED_FEATURES
        for argument in ("--disable", feature)
    ]
    return [
        *codex_command_prefix(),
        "exec",
        "--json",
        "--skip-git-repo-check",
        *disabled_feature_args,
        "-c",
        f'model_reasoning_effort="{codex_reasoning_effort(job)}"',
        "--model",
        codex_model(),
        "--cd",
        str(work_dir),
        "--sandbox",
        "read-only",
        "--output-schema",
        str(output_schema_file),
        "--output-last-message",
        str(last_message_file),
        "-",
    ]


def codex_exec_work_dir() -> Path:
    CODEX_EXEC_WORK_DIR.mkdir(parents=True, exist_ok=True)
    return CODEX_EXEC_WORK_DIR.resolve()


def codex_saved_login_env() -> dict[str, str]:
    env = os.environ.copy()
    for variable_name in CODEX_SAVED_LOGIN_BLOCKED_ENV:
        env.pop(variable_name, None)
    return env


def bridge_backend() -> str:
    backend = os.getenv("CODEX_BRIDGE_WORKER_BACKEND", os.getenv("CODEX_BRIDGE_BACKEND", "codex")).strip().lower()
    if backend in {"gemini_flash", "gemini-flash", "google_flash", "google-flash"}:
        return "gemini_flash"
    if backend in {"gemini_31_flash_lite", "gemini-31-flash-lite", "gemini_3_1_flash_lite", "gemini-3.1-flash-lite", "gemini31_lite"}:
        return "gemini_31_flash_lite"
    if backend in {"gemini", "google_ai", "google-ai", "googleai"}:
        return "gemini_31_flash_lite"
    if backend in {"gemma", "gemma3", "gemma-3", "google_gemma", "google-gemma"}:
        return "gemma"
    if backend in {"groq", "groqcloud"}:
        return "groq"
    if backend in {"cerebras", "cerebras_cloud", "cerebras-cloud"}:
        return "cerebras"
    if backend in {"mistral", "mistralai", "mistral_ai", "mistral-ai"}:
        return "mistral"
    return "codex"


def gemini_model() -> str:
    if bridge_backend() == "gemma":
        model = os.getenv("CODEX_BRIDGE_GEMMA_MODEL", os.getenv("GEMMA_MODEL", DEFAULT_GEMMA_MODEL)).strip()
        return model or DEFAULT_GEMMA_MODEL
    if bridge_backend() == "gemini_31_flash_lite":
        model = os.getenv("CODEX_BRIDGE_GEMINI_31_FLASH_LITE_MODEL", os.getenv("GEMINI_31_FLASH_LITE_MODEL", DEFAULT_GEMINI_31_FLASH_LITE_MODEL)).strip()
        return model or DEFAULT_GEMINI_31_FLASH_LITE_MODEL
    if bridge_backend() == "gemini_flash":
        model = os.getenv("CODEX_BRIDGE_GEMINI_FLASH_MODEL", os.getenv("GEMINI_FLASH_MODEL", DEFAULT_GEMINI_FLASH_MODEL)).strip()
        return model or DEFAULT_GEMINI_FLASH_MODEL
    model = os.getenv("CODEX_BRIDGE_GEMINI_MODEL", os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)).strip()
    return model or DEFAULT_GEMINI_MODEL


def gemini_high_demand_fallback_model(current_model: str) -> str:
    return ""


def gemini_api_keys() -> list[tuple[str, str]]:
    value = os.getenv("CODEX_BRIDGE_GEMINI_API_KEY", "").strip()
    return [("CODEX_BRIDGE_GEMINI_API_KEY", value)] if value else []


def select_gemini_api_key(
    job: dict[str, Any],
    model: str,
    fallback_attempt: int = 0,
    excluded_key_names: tuple[str, ...] = (),
) -> tuple[str, str]:
    keys = [(name, value) for name, value in gemini_api_keys() if name not in set(excluded_key_names)]
    if not keys:
        raise BridgeError("Ceviri motoru Gemini API key bulunamadi: CODEX_BRIDGE_GEMINI_API_KEY ayarla")
    return keys[0]


def gemini_request_spacing_seconds(model: str) -> float:
    model_name = str(model or "").lower()
    if model_name == DEFAULT_GEMINI_31_FLASH_LITE_MODEL:
        default_value = DEFAULT_GEMINI_31_FLASH_LITE_REQUEST_SPACING_SECONDS
        env_name = "CODEX_BRIDGE_GEMINI_31_FLASH_LITE_REQUEST_SPACING_SECONDS"
    else:
        default_value = DEFAULT_GEMINI_FLASH_REQUEST_SPACING_SECONDS
        env_name = "CODEX_BRIDGE_GEMINI_FLASH_REQUEST_SPACING_SECONDS"
    try:
        return max(0.0, float(os.getenv(env_name, str(default_value)).strip() or default_value))
    except ValueError:
        return default_value


def wait_for_gemini_request_slot(model: str) -> float:
    spacing = gemini_request_spacing_seconds(model)
    if spacing <= 0:
        return 0.0
    state_file = USAGE_DIR / "gemini_request_spacing_state.json"
    lock_file = USAGE_DIR / "gemini_request_spacing.lock"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+", encoding="utf-8") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            try:
                state = read_json(state_file) if state_file.exists() else {}
            except Exception:
                state = {}
            key = str(model or "unknown")
            now = time.time()
            last_started = float(state.get(key, 0.0) or 0.0)
            wait_seconds = max(0.0, spacing - (now - last_started))
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                now = time.time()
            state[key] = now
            write_json(state_file, state)
            return round(wait_seconds, 3)
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def bridge_model_name() -> str:
    backend = bridge_backend()
    if backend in {"gemini_flash", "gemini_31_flash_lite", "gemma"}:
        return gemini_model()
    if backend == "groq":
        return groq_model()
    if backend == "cerebras":
        return cerebras_model()
    if backend == "mistral":
        return mistral_model()
    return codex_model()


def groq_model() -> str:
    model = os.getenv("CODEX_BRIDGE_GROQ_MODEL", os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)).strip()
    return model or DEFAULT_GROQ_MODEL


def groq_api_key() -> str:
    for name in ("CODEX_BRIDGE_GROQ_API_KEY", "GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise BridgeError("Groq API key bulunamadi: CODEX_BRIDGE_GROQ_API_KEY veya GROQ_API_KEY_1 ayarla")


def cerebras_model() -> str:
    model = os.getenv("CODEX_BRIDGE_CEREBRAS_MODEL", os.getenv("CEREBRAS_MODEL", DEFAULT_CEREBRAS_MODEL)).strip()
    return model or DEFAULT_CEREBRAS_MODEL


def cerebras_api_key() -> str:
    for name in ("CODEX_BRIDGE_CEREBRAS_API_KEY", "CEREBRAS_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise BridgeError("Cerebras API key bulunamadi: CODEX_BRIDGE_CEREBRAS_API_KEY veya CEREBRAS_API_KEY ayarla")


def mistral_model() -> str:
    model = os.getenv("CODEX_BRIDGE_MISTRAL_MODEL", os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL)).strip()
    return model or DEFAULT_MISTRAL_MODEL


def mistral_api_key() -> str:
    for name in ("CODEX_BRIDGE_MISTRAL_API_KEY", "MISTRAL_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise BridgeError("Mistral API key bulunamadi: CODEX_BRIDGE_MISTRAL_API_KEY veya MISTRAL_API_KEY ayarla")


def classify_gemini_error(status_code: int, text: str) -> dict[str, Any]:
    retryable = status_code in {408, 500, 502, 503, 504}
    retry_seconds = 600 if retryable else 0
    retry_at = (datetime.now() + timedelta(seconds=retry_seconds)).isoformat(timespec="seconds") if retryable else ""
    return {
        "error_type": "gemini_api_error" if not retryable else "gemini_api_temporary",
        "retryable": retryable,
        "retry_after_at": retry_at,
        "retry_after_seconds": retry_seconds,
        "retry_reason": "temporary_gemini_api" if retryable else "gemini_api_error",
        "status_code": status_code,
        "response_text": str(text or "")[:2000],
    }


def is_gemini_high_demand_error(status_code: int, text: str) -> bool:
    lowered = str(text or "").lower()
    return status_code == 503 and (
        "high demand" in lowered
        or "overloaded" in lowered
        or "temporarily overloaded" in lowered
        or "running out of capacity" in lowered
        or "capacity" in lowered
    )


def gemini_high_demand_retry_delays(model: str) -> tuple[float, ...]:
    if str(model or "").strip().lower() == DEFAULT_GEMINI_31_FLASH_LITE_MODEL:
        return GEMINI_31_FLASH_LITE_HIGH_DEMAND_RETRY_DELAYS
    return ()


def is_gemini_invalid_api_key_error(status_code: int, text: str) -> bool:
    lowered = str(text or "").lower()
    return status_code == 400 and (
        "api_key_invalid" in lowered
        or "api key not valid" in lowered
    )


def gemini_candidate_meta(response_data: dict[str, Any]) -> dict[str, Any]:
    candidates = response_data.get("candidates")
    candidate = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
    finish_reason = str(candidate.get("finishReason") or candidate.get("finish_reason") or "")
    finish_message = str(candidate.get("finishMessage") or candidate.get("finish_message") or "")
    return {
        "finish_reason": finish_reason,
        "finish_message": finish_message,
        "safety_ratings": candidate.get("safetyRatings") if isinstance(candidate.get("safetyRatings"), list) else [],
    }


def gemini_max_tokens_error_details(meta: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        **meta,
        "error_type": "gemini_model_output_limit",
        "retryable": True,
        "retry_after_at": "",
        "retry_after_seconds": 0,
        "retry_reason": "model_output_limit",
        "response_text_excerpt": str(text or "")[-1000:],
    }


def run_bridge_model(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    backend = bridge_backend()
    if backend in {"gemini_flash", "gemini_31_flash_lite", "gemma"}:
        return run_gemini(job, timeout_seconds)
    if backend == "groq":
        return run_openai_compatible(
            job,
            timeout_seconds,
            provider="groq",
            backend="groq",
            model=groq_model(),
            api_key=groq_api_key(),
            url="https://api.groq.com/openai/v1/chat/completions",
            temperature=float(os.getenv("CODEX_BRIDGE_GROQ_TEMPERATURE", "0.25")),
            max_tokens=int(os.getenv("CODEX_BRIDGE_GROQ_MAX_OUTPUT_TOKENS", "8192")),
        )
    if backend == "cerebras":
        return run_openai_compatible(
            job,
            timeout_seconds,
            provider="cerebras",
            backend="cerebras",
            model=cerebras_model(),
            api_key=cerebras_api_key(),
            url="https://api.cerebras.ai/v1/chat/completions",
            temperature=float(os.getenv("CODEX_BRIDGE_CEREBRAS_TEMPERATURE", "0.25")),
            max_tokens=int(os.getenv("CODEX_BRIDGE_CEREBRAS_MAX_OUTPUT_TOKENS", "8192")),
        )
    if backend == "mistral":
        return run_openai_compatible(
            job,
            timeout_seconds,
            provider="mistral",
            backend="mistral",
            model=mistral_model(),
            api_key=mistral_api_key(),
            url="https://api.mistral.ai/v1/chat/completions",
            temperature=float(os.getenv("CODEX_BRIDGE_MISTRAL_TEMPERATURE", "0.25")),
            max_tokens=int(os.getenv("CODEX_BRIDGE_MISTRAL_MAX_OUTPUT_TOKENS", "8192")),
        )
    return run_codex(job, timeout_seconds)


def normalize_process_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def codex_cli_usage(stdout: str) -> dict[str, Any]:
    usage_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    for line in reversed(str(stdout or "").splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            continue
        normalized = {name: max(0, int(usage.get(name) or 0)) for name in usage_fields}
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]
        normalized["token_usage_available"] = True
        normalized["token_usage_source"] = "codex_cli_turn_completed"
        return normalized
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "token_usage_available": False,
        "token_usage_source": "codex_cli_turn_completed_missing",
    }


def run_codex(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    job_id = safe_name(str(job["job_id"]))
    prompt = build_prompt(job)
    last_message_file = TMP_DIR / f"{job_id}_last_message.json"
    stdout_file = LOGS_DIR / f"{job_id}_codex_stdout.txt"
    stderr_file = LOGS_DIR / f"{job_id}_codex_stderr.txt"

    output_schema_file = write_codex_output_schema(job)
    command = build_codex_command(last_message_file, output_schema_file, job)
    work_dir = codex_exec_work_dir()
    started = time.time()
    try:
        timeout_seconds = kalan_sure(timeout_seconds)
        completed = agacli_calistir(
            command,
            input_text=prompt,
            cwd=str(work_dir),
            env=codex_saved_login_env(),
            timeout=timeout_seconds,
            creationflags=NO_WINDOW_FLAGS,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - started
        stdout = normalize_process_text(exc.stdout)
        stderr = normalize_process_text(exc.stderr)
        stdout_file.write_text(stdout, encoding="utf-8")
        stderr_file.write_text(stderr, encoding="utf-8")
        session_id = extract_session_id(stderr)
        session_cleanup = cleanup_codex_session(session_id)
        retry_at = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
        details = {
            "error_type": "codex_timeout",
            "retryable": True,
            "retry_after_at": retry_at,
            "retry_after_seconds": 600,
            "retry_reason": "timeout",
            "timeout_seconds": timeout_seconds,
            "duration_seconds": round(duration, 3),
            "session_id": session_cleanup.get("session_id", ""),
            "session_cleanup": session_cleanup.get("status", ""),
        }
        raise BridgeError(
            format_bridge_error("Codex CLI timeout oldu", details),
            error_type=details["error_type"],
            retry_after_at=details["retry_after_at"],
            retry_after_seconds=details["retry_after_seconds"],
            retry_reason=details["retry_reason"],
            retryable=details["retryable"],
        ) from exc
    finally:
        output_schema_file.unlink(missing_ok=True)
    duration = time.time() - started
    stdout_file.write_text(completed.stdout or "", encoding="utf-8")
    stderr_file.write_text(completed.stderr or "", encoding="utf-8")
    session_id = extract_session_id(completed.stderr or "")
    session_cleanup = cleanup_codex_session(session_id)
    usage = codex_cli_usage(completed.stdout or "")

    meta = {
        "returncode": completed.returncode,
        "backend": "codex",
        "duration_seconds": round(duration, 3),
        "stdout_file": str(stdout_file),
        "stderr_file": str(stderr_file),
        "last_message_file": str(last_message_file),
        "model": codex_model(),
        "reasoning_effort": codex_reasoning_effort(job),
        "working_directory": str(work_dir),
        "sandbox": "read-only",
        "disabled_features": list(CODEX_EXEC_DISABLED_FEATURES),
        "authentication_mode": "saved_chatgpt_login",
        "child_api_key_environment_filtered": True,
        "codex_session_cleanup": session_cleanup,
        "execution_mode": "codex_exec",
        "pricing_status": "priced_configured" if codex_model() in CODEX_PRICED_MODELS else "not_available_exact_model_price_not_verified",
        **usage,
    }
    if completed.returncode != 0:
        details = classify_codex_cli_error(completed.stderr or "", completed.stdout or "")
        details.update({
            "returncode": completed.returncode,
            "session_id": session_cleanup.get("session_id", ""),
            "session_cleanup": session_cleanup.get("status", ""),
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
            "last_message_file": str(last_message_file),
        })
        raise BridgeError(
            format_bridge_error("Codex CLI basarisiz oldu", details),
            error_type=str(details.get("error_type") or "codex_cli_error"),
            retry_after_at=str(details.get("retry_after_at") or ""),
            retry_after_seconds=int(details.get("retry_after_seconds") or 0),
            retry_reason=str(details.get("retry_reason") or ""),
            retryable=bool(details.get("retryable", False)),
        )

    job_path_value = Path(str(job.get("_job_file") or ""))
    record_api_usage({
        "job_id": str(job.get("job_id") or ""),
        "job_file": str(job_path_value) if str(job_path_value) != "." else "",
        "provider": "openai",
        "backend": "codex",
        "model": meta["model"],
        "reasoning_effort": meta["reasoning_effort"],
        "execution_mode": meta["execution_mode"],
        "status": "success",
        "duration_seconds": meta["duration_seconds"],
        "input_tokens": meta["input_tokens"],
        "cached_input_tokens": meta["cached_input_tokens"],
        "output_tokens": meta["output_tokens"],
        "reasoning_output_tokens": meta["reasoning_output_tokens"],
        "total_tokens": meta["total_tokens"],
        "token_usage_available": meta["token_usage_available"],
        "token_usage_source": meta["token_usage_source"],
        "pricing_status": meta["pricing_status"],
        "timestamp": now_iso(),
    })

    if last_message_file.exists():
        raw = last_message_file.read_text(encoding="utf-8", errors="replace")
    else:
        raw = completed.stdout or ""
    return extract_json(raw), meta


def classify_openai_compatible_error(provider: str, status_code: int, text: str) -> dict[str, Any]:
    retryable = status_code in {408, 429, 500, 502, 503, 504}
    retry_seconds = 600 if retryable else 0
    retry_at = (datetime.now() + timedelta(seconds=retry_seconds)).isoformat(timespec="seconds") if retryable else ""
    return {
        "error_type": f"{provider}_api_error" if not retryable else f"{provider}_api_temporary",
        "retryable": retryable,
        "retry_after_at": retry_at,
        "retry_after_seconds": retry_seconds,
        "retry_reason": f"{provider}_temporary_or_rate_limit" if retryable else f"{provider}_api_error",
        "status_code": status_code,
        "response_text": str(text or "")[:2000],
    }


def run_openai_compatible(
    job: dict[str, Any],
    timeout_seconds: int,
    provider: str,
    backend: str,
    model: str,
    api_key: str,
    url: str,
    temperature: float,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    job_id = safe_name(str(job["job_id"]))
    prompt = build_prompt(job) + "\n\nSadece geçerli JSON döndür. Markdown, açıklama veya kod bloğu yazma."
    stdout_file = LOGS_DIR / f"{job_id}_{backend}_stdout.txt"
    stderr_file = LOGS_DIR / f"{job_id}_{backend}_stderr.txt"
    job_path_value = Path(str(job.get("_job_file") or ""))
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    estimated_input_tokens = estimate_text_tokens(prompt)
    api_timeout_seconds = timing_repair_api_timeout_seconds(job, timeout_seconds)
    # S310: adres api_url_dogrula ile yalnız https + izinli sağlayıcı; yönlendirme de yalnız https (_API_ACICI).
    request = urllib.request.Request(  # noqa: S310
        api_url_dogrula(url),
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "dubworld-codex-bridge/1.0",
        },
    )
    started = time.time()
    try:
        with _API_ACICI.open(request, timeout=api_timeout_seconds) as response:
            raw_bytes = response.read()
            response_headers = usage_headers(response.headers)
    except urllib.error.HTTPError as exc:
        duration = time.time() - started
        raw_error = exc.read().decode("utf-8", errors="replace")
        stdout_file.write_text("", encoding="utf-8")
        stderr_file.write_text(raw_error, encoding="utf-8")
        details = classify_openai_compatible_error(provider, int(exc.code), raw_error)
        details.update({
            "duration_seconds": round(duration, 3),
            "model": model,
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
            "rate_limit_headers": usage_headers(exc.headers),
        })
        record_api_usage({
            "job_id": str(job.get("job_id") or ""),
            "job_file": str(job_path_value) if str(job_path_value) != "." else "",
            "provider": provider,
            "backend": backend,
            "model": model,
            "status": "failed",
            "error_type": str(details.get("error_type") or ""),
            "status_code": int(exc.code),
            "duration_seconds": round(duration, 3),
            "estimated_input_tokens": estimated_input_tokens,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "rate_limit_headers": details.get("rate_limit_headers", {}),
            "response_text_excerpt": str(raw_error or "")[:1000],
        })
        raise BridgeError(
            format_bridge_error(f"{provider} API basarisiz oldu", details),
            error_type=str(details.get("error_type") or f"{provider}_api_error"),
            retry_after_at=str(details.get("retry_after_at") or ""),
            retry_after_seconds=int(details.get("retry_after_seconds") or 0),
            retry_reason=str(details.get("retry_reason") or ""),
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        duration = time.time() - started
        stdout_file.write_text("", encoding="utf-8")
        stderr_file.write_text(str(exc), encoding="utf-8")
        retry_at = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
        details = {
            "error_type": f"{provider}_temporary_network",
            "retryable": True,
            "retry_after_at": retry_at,
            "retry_after_seconds": 600,
            "retry_reason": "temporary_network",
            "duration_seconds": round(duration, 3),
            "model": model,
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
        }
        record_api_usage({
            "job_id": str(job.get("job_id") or ""),
            "job_file": str(job_path_value) if str(job_path_value) != "." else "",
            "provider": provider,
            "backend": backend,
            "model": model,
            "status": "failed",
            "error_type": details["error_type"],
            "status_code": 0,
            "duration_seconds": round(duration, 3),
            "estimated_input_tokens": estimated_input_tokens,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "rate_limit_headers": {},
            "response_text_excerpt": str(exc)[:1000],
        })
        raise BridgeError(
            format_bridge_error(f"{provider} API ag hatasi", details),
            error_type=details["error_type"],
            retry_after_at=details["retry_after_at"],
            retry_after_seconds=details["retry_after_seconds"],
            retry_reason=details["retry_reason"],
        ) from exc
    duration = time.time() - started
    raw_response = raw_bytes.decode("utf-8", errors="replace")
    response_data = json.loads(raw_response)
    choices = response_data.get("choices") if isinstance(response_data.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    text = str(message.get("content") or "").strip()
    usage_metadata = response_data.get("usage") if isinstance(response_data.get("usage"), dict) else {}
    input_tokens = int(usage_metadata.get("prompt_tokens") or 0)
    output_tokens = int(usage_metadata.get("completion_tokens") or 0)
    total_tokens = int(usage_metadata.get("total_tokens") or (input_tokens + output_tokens))
    stdout_file.write_text(text, encoding="utf-8")
    stderr_file.write_text("", encoding="utf-8")
    meta = {
        "backend": backend,
        "model": model,
        "duration_seconds": round(duration, 3),
        "stdout_file": str(stdout_file),
        "stderr_file": str(stderr_file),
        "usage_metadata": usage_metadata,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_input_tokens": estimated_input_tokens,
        "rate_limit_headers": response_headers,
    }
    record_api_usage({
        "job_id": str(job.get("job_id") or ""),
        "job_file": str(job_path_value) if str(job_path_value) != "." else "",
        "provider": provider,
        "backend": backend,
        "model": model,
        "status": "success",
        "error_type": "",
        "status_code": 200,
        "duration_seconds": round(duration, 3),
        "estimated_input_tokens": estimated_input_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "usage_metadata": usage_metadata,
        "rate_limit_headers": response_headers,
    })
    if not text:
        raise BridgeError(format_bridge_error(f"{provider} API bos cevap dondurdu", {**meta, "error_type": f"{provider}_empty_response", "retryable": False}))
    return extract_json(text), meta


def run_gemini(
    job: dict[str, Any],
    timeout_seconds: int,
    model_override: str = "",
    fallback_attempt: int = 0,
    excluded_key_names: tuple[str, ...] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    job_id = safe_name(str(job["job_id"]))
    backend_name = bridge_backend()
    selected_prompt_file = gemini_prompt_file()
    prompt = build_prompt(job, selected_prompt_file) + "\n\nSadece geçerli JSON döndür. Markdown, açıklama veya kod bloğu yazma."
    log_suffix = "" if fallback_attempt <= 0 else f"_fallback_{fallback_attempt}"
    stdout_file = LOGS_DIR / f"{job_id}_gemini{log_suffix}_stdout.txt"
    stderr_file = LOGS_DIR / f"{job_id}_gemini{log_suffix}_stderr.txt"
    model = model_override.strip() or gemini_model()
    job_path_value = Path(str(job.get("_job_file") or ""))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    strict_contract = gemini_strict_segment_contract_enabled()
    temperature = gemini_temperature(job)
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }
    if strict_contract:
        body["generationConfig"]["responseFormat"] = {
            "text": {
                "mimeType": "APPLICATION_JSON",
                "schema": gemini_result_response_json_schema(job),
            }
        }
    else:
        body["generationConfig"]["responseMimeType"] = "application/json"
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    estimated_input_tokens = estimate_text_tokens(prompt)
    api_timeout_seconds = timing_repair_api_timeout_seconds(job, timeout_seconds)
    api_key_name, api_key_value = select_gemini_api_key(job, model, fallback_attempt, excluded_key_names)
    spacing_wait_seconds = wait_for_gemini_request_slot(model)
    # S310: adres api_url_dogrula ile yalnız https + izinli sağlayıcı; yönlendirme de yalnız https (_API_ACICI).
    request = urllib.request.Request(  # noqa: S310
        api_url_dogrula(url),
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "x-goog-api-key": api_key_value,
        },
    )
    retry_delays = gemini_high_demand_retry_delays(model)
    high_demand_retry_attempt = 0
    append_jsonl(LOGS_DIR / f"{job_id}.jsonl", {
        "event": "api_request_started",
        "provider": "google",
        "backend": backend_name,
        "model": model,
        "timeout_seconds": api_timeout_seconds,
        "worker_timeout_seconds": timeout_seconds,
        "timing_repair": is_timing_repair_job(job),
        "estimated_input_tokens": estimated_input_tokens,
        "fallback_attempt": fallback_attempt,
        "api_key_name": api_key_name,
        "spacing_wait_seconds": spacing_wait_seconds,
        "temperature": temperature,
        "strict_segment_contract": strict_contract,
        "response_format_schema": strict_contract,
    })
    while True:
        started = time.time()
        try:
            with _API_ACICI.open(request, timeout=api_timeout_seconds) as response:
                raw_bytes = response.read()
                response_headers = usage_headers(response.headers)
            break
        except urllib.error.HTTPError as exc:
            duration = time.time() - started
            raw_error = exc.read().decode("utf-8", errors="replace")
            stdout_file.write_text("", encoding="utf-8")
            stderr_file.write_text(raw_error, encoding="utf-8")
            details = classify_gemini_error(int(exc.code), raw_error)
            details.update({
                "duration_seconds": round(duration, 3),
                "model": model,
                "stdout_file": str(stdout_file),
                "stderr_file": str(stderr_file),
                "timeout_seconds": api_timeout_seconds,
                "worker_timeout_seconds": timeout_seconds,
                "rate_limit_headers": usage_headers(exc.headers),
                "api_key_name": api_key_name,
                "spacing_wait_seconds": spacing_wait_seconds,
                "high_demand_retry_attempt": high_demand_retry_attempt,
            })
            record_api_usage({
                "job_id": str(job.get("job_id") or ""),
                "job_file": str(job_path_value) if str(job_path_value) != "." else "",
                "provider": "google",
                "backend": backend_name,
                "model": model,
                "status": "failed",
                "error_type": str(details.get("error_type") or ""),
                "status_code": int(exc.code),
                "duration_seconds": round(duration, 3),
                "estimated_input_tokens": estimated_input_tokens,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "rate_limit_headers": details.get("rate_limit_headers", {}),
                "response_text_excerpt": str(raw_error or "")[:1000],
                "api_key_name": api_key_name,
                "spacing_wait_seconds": spacing_wait_seconds,
                "high_demand_retry_attempt": high_demand_retry_attempt,
            })
            if is_gemini_invalid_api_key_error(int(exc.code), raw_error):
                next_excluded_key_names = tuple(dict.fromkeys((*excluded_key_names, api_key_name)))
                if len(next_excluded_key_names) < len(gemini_api_keys()):
                    append_jsonl(LOGS_DIR / f"{job_id}.jsonl", {
                        "event": "api_key_invalid_retry",
                        "provider": "google",
                        "backend": backend_name,
                        "model": model,
                        "invalid_api_key_name": api_key_name,
                        "excluded_key_names": list(next_excluded_key_names),
                        "status_code": int(exc.code),
                        "duration_seconds": round(duration, 3),
                    })
                    return run_gemini(
                        job,
                        timeout_seconds,
                        model_override=model,
                        fallback_attempt=fallback_attempt,
                        excluded_key_names=next_excluded_key_names,
                    )
            if is_gemini_high_demand_error(int(exc.code), raw_error) and high_demand_retry_attempt < len(retry_delays):
                wait_seconds = retry_delays[high_demand_retry_attempt]
                high_demand_retry_attempt += 1
                append_jsonl(LOGS_DIR / f"{job_id}.jsonl", {
                    "event": "api_high_demand_same_model_retry",
                    "provider": "google",
                    "backend": backend_name,
                    "model": model,
                    "attempt": high_demand_retry_attempt,
                    "max_attempts": len(retry_delays),
                    "wait_seconds": wait_seconds,
                    "status_code": int(exc.code),
                    "error_type": str(details.get("error_type") or ""),
                    "api_key_name": api_key_name,
                    "segment_ids": [str(segment.get("id")) for segment in job.get("segments", []) if isinstance(segment, dict)],
                    "job_id": str(job.get("job_id") or ""),
                })
                time.sleep(wait_seconds)
                continue
            if is_gemini_high_demand_error(int(exc.code), raw_error) and retry_delays:
                details["retry_after_at"] = ""
                details["retry_after_seconds"] = 0
                details["retry_reason"] = "high_demand"
            fallback_model = gemini_high_demand_fallback_model(model)
            if fallback_attempt == 0 and is_gemini_high_demand_error(int(exc.code), raw_error) and fallback_model:
                append_jsonl(LOGS_DIR / f"{job_id}.jsonl", {
                    "event": "api_high_demand_fallback",
                    "provider": "google",
                    "backend": backend_name,
                    "from_model": model,
                    "to_model": fallback_model,
                    "status_code": int(exc.code),
                    "duration_seconds": round(duration, 3),
                    "reason": "gemini_high_demand",
                })
                return run_gemini(
                    job,
                    timeout_seconds,
                    model_override=fallback_model,
                    fallback_attempt=fallback_attempt + 1,
                    excluded_key_names=excluded_key_names,
                )
            raise BridgeError(
                format_bridge_error("Gemini API basarisiz oldu", details),
                error_type=str(details.get("error_type") or "gemini_api_error"),
                retry_after_at=str(details.get("retry_after_at") or ""),
                retry_after_seconds=int(details.get("retry_after_seconds") or 0),
                retry_reason=str(details.get("retry_reason") or ""),
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            duration = time.time() - started
            stdout_file.write_text("", encoding="utf-8")
            stderr_file.write_text(str(exc), encoding="utf-8")
            retry_at = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
            details = {
                "error_type": "gemini_temporary_network",
                "retryable": True,
                "retry_after_at": retry_at,
                "retry_after_seconds": 600,
                "retry_reason": "temporary_network",
                "duration_seconds": round(duration, 3),
                "model": model,
                "stdout_file": str(stdout_file),
                "stderr_file": str(stderr_file),
                "timeout_seconds": api_timeout_seconds,
                "worker_timeout_seconds": timeout_seconds,
                "api_key_name": api_key_name,
                "spacing_wait_seconds": spacing_wait_seconds,
            }
            record_api_usage({
                "job_id": str(job.get("job_id") or ""),
                "job_file": str(job_path_value) if str(job_path_value) != "." else "",
                "provider": "google",
                "backend": backend_name,
                "model": model,
                "status": "failed",
                "error_type": details["error_type"],
                "status_code": 0,
                "duration_seconds": round(duration, 3),
                "estimated_input_tokens": estimated_input_tokens,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "rate_limit_headers": {},
                "response_text_excerpt": str(exc)[:1000],
                "api_key_name": api_key_name,
                "spacing_wait_seconds": spacing_wait_seconds,
            })
            raise BridgeError(
                format_bridge_error("Gemini API ag hatasi", details),
                error_type=details["error_type"],
                retry_after_at=details["retry_after_at"],
                retry_after_seconds=details["retry_after_seconds"],
                retry_reason=details["retry_reason"],
            ) from exc
    duration = time.time() - started
    raw_response = raw_bytes.decode("utf-8", errors="replace")
    response_data = json.loads(raw_response)
    response_candidate_meta = gemini_candidate_meta(response_data)
    candidates = response_data.get("candidates")
    candidate = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
    content = candidate.get("content") if isinstance(candidate.get("content"), dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
    usage_metadata = response_data.get("usageMetadata") if isinstance(response_data.get("usageMetadata"), dict) else {}
    input_tokens = int(usage_metadata.get("promptTokenCount") or 0)
    output_tokens = int(usage_metadata.get("candidatesTokenCount") or 0)
    total_tokens = int(usage_metadata.get("totalTokenCount") or (input_tokens + output_tokens))
    stdout_file.write_text(text, encoding="utf-8")
    stderr_file.write_text("", encoding="utf-8")
    meta = {
        "backend": backend_name,
        "model": model,
        "duration_seconds": round(duration, 3),
        "timeout_seconds": api_timeout_seconds,
        "worker_timeout_seconds": timeout_seconds,
        "stdout_file": str(stdout_file),
        "stderr_file": str(stderr_file),
        "usage_metadata": usage_metadata,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_input_tokens": estimated_input_tokens,
        "rate_limit_headers": response_headers,
        "prompt_file": str(selected_prompt_file),
        "api_key_name": api_key_name,
        "spacing_wait_seconds": spacing_wait_seconds,
        "temperature": temperature,
        "strict_segment_contract": strict_contract,
        "response_format_schema": strict_contract,
        **response_candidate_meta,

    }
    finish_reason = str(response_candidate_meta.get("finish_reason") or "")
    record_api_usage({
        "job_id": str(job.get("job_id") or ""),
        "job_file": str(job_path_value) if str(job_path_value) != "." else "",
        "provider": "google",
        "backend": backend_name,
        "model": model,
        "status": "failed" if finish_reason == "MAX_TOKENS" else "success",
        "error_type": "gemini_model_output_limit" if finish_reason == "MAX_TOKENS" else "",
        "status_code": 200,
        "duration_seconds": round(duration, 3),
        "estimated_input_tokens": estimated_input_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "usage_metadata": usage_metadata,
        "rate_limit_headers": response_headers,
        "finish_reason": response_candidate_meta.get("finish_reason", ""),
        "finish_message": response_candidate_meta.get("finish_message", ""),
        "response_text_excerpt": str(text or "")[-1000:] if finish_reason == "MAX_TOKENS" else "",
        "api_key_name": api_key_name,
        "spacing_wait_seconds": spacing_wait_seconds,
    })
    if finish_reason == "MAX_TOKENS":
        details = gemini_max_tokens_error_details(meta, text)
        raise BridgeError(
            format_bridge_error("Gemini cevabi model output sinirinda kesildi", details),
            error_type="gemini_model_output_limit",
            retry_after_at="",
            retry_after_seconds=0,
            retry_reason="model_output_limit",
        )
    if not text:
        raise BridgeError(format_bridge_error("Gemini API bos cevap dondurdu", {**meta, "error_type": "gemini_empty_response", "retryable": False}))
    result = extract_json(text)
    kept_terms_normalizations = normalize_gemini_kept_terms(job, result)
    if kept_terms_normalizations:
        meta["gemini_kept_terms_normalizations"] = kept_terms_normalizations
    fragment_candidate_normalizations = normalize_gemini_fragment_candidates(job, result)
    if fragment_candidate_normalizations:
        meta["gemini_fragment_candidate_normalizations"] = fragment_candidate_normalizations
    return result, meta


def write_status(job_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    payload = {
        "job_id": job_id,
        "status": status,
        "updated_at": now_iso(),
    }
    if extra:
        payload.update(extra)
    write_json(WORK_ROOT / "status.json", payload)


def process_job(job_file: Path, mock: bool, timeout_seconds: int, keep_job: bool = False) -> Path:
    job = read_json(job_file)
    job["_job_file"] = str(job_file)
    validate_job(job)
    job_id = safe_name(str(job["job_id"]))
    log_file = LOGS_DIR / f"{job_id}.jsonl"
    selected_backend = bridge_backend() if not mock else "mock"
    selected_model = bridge_model_name() if not mock else "mock"
    append_jsonl(log_file, {
        "event": "started",
        "job_file": str(job_file),
        "mock": mock,
        "backend": selected_backend,
        "model": selected_model,
    })
    write_status(str(job["job_id"]), "processing", {
        "mock": mock,
        "backend": selected_backend,
        "model": selected_model,
    })

    if mock:
        result = run_mock(job)
        meta = {"mode": "mock"}
    else:
        result, meta = run_codex_with_contract_retry(job, timeout_seconds)

    if job.get("task_type") != "full_text_translation":
        candidate_normalizations = normalize_result_candidates(job, result)
        if candidate_normalizations:
            meta["candidate_normalizations"] = candidate_normalizations
        kept_terms_spoken_normalizations = normalize_kept_terms_to_spoken_candidates(result, job)
        if kept_terms_spoken_normalizations:
            meta["kept_terms_spoken_normalizations"] = kept_terms_spoken_normalizations
    validate_result(job, result)
    if not mock:
        validate_output_language(job, result)
    result["_bridge_meta"] = meta
    result_file = OUTBOX_DIR / f"{job_id}_result.json"
    write_json(result_file, result)
    if not keep_job:
        job_file.unlink(missing_ok=True)
    append_jsonl(log_file, {"event": "completed", "result_file": str(result_file), "meta": meta})
    write_status(str(job["job_id"]), "completed", {"result_file": str(result_file)})
    return result_file


def fail_job(job_file: Path, error: Exception) -> Path:
    job_id = job_file.stem
    try:
        job = read_json(job_file)
        job_id = safe_name(str(job.get("job_id") or job_file.stem))
    except Exception:
        job = None

    error_file = FAILED_DIR / f"{job_id}_error.json"
    payload = {
        "job_id": job_id,
        "status": "failed",
        "error": str(error),
        "error_type": getattr(error, "error_type", "bridge_error"),
        "retry_after_at": getattr(error, "retry_after_at", ""),
        "retry_after_seconds": getattr(error, "retry_after_seconds", 0),
        "retry_reason": getattr(error, "retry_reason", ""),
        "retryable": bool(getattr(error, "retryable", False)),
        "failed_at": now_iso(),
        "job_file": str(job_file),
    }
    write_json(error_file, payload)
    if job_file.exists():
        shutil.move(str(job_file), str(FAILED_DIR / f"{job_id}.json"))
    append_jsonl(LOGS_DIR / f"{job_id}.jsonl", {"event": "failed", "error": str(error), "error_file": str(error_file)})
    write_status(job_id, "failed", {"error_file": str(error_file), "error": str(error)})
    return error_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Ceviri motoru worker")
    parser.add_argument("--mock", action="store_true", help="Codex CLI cagirmadan deterministik test sonucu uret")
    parser.add_argument("--timeout", type=int, default=900, help="Codex CLI timeout saniye")
    parser.add_argument("--job", type=Path, help="Inbox yerine belirli job dosyasini isle")
    parser.add_argument("--keep-job", action="store_true", help="--job ile verilen dosyayi basaridan sonra silme")
    args = parser.parse_args()

    ensure_dirs()
    job_file = args.job if args.job else acquire_job()
    if job_file is None:
        print("Bekleyen job yok.")
        return 0

    job_id = job_file.stem
    try:
        is_butcesi_baslat(args.timeout)
        result_file = process_job(job_file, mock=args.mock, timeout_seconds=args.timeout, keep_job=args.keep_job)
        print(result_file)
        return 0
    except Exception as exc:
        error_file = fail_job(job_file, exc)
        error_payload = {
            "job_id": job_id,
            "status": "failed",
            "error_type": getattr(exc, "error_type", "bridge_error"),
            "retry_after_at": getattr(exc, "retry_after_at", ""),
            "retry_after_seconds": getattr(exc, "retry_after_seconds", 0),
            "retry_reason": getattr(exc, "retry_reason", ""),
            "retryable": bool(getattr(exc, "retryable", False)),
        }
        print(format_bridge_error(str(exc), error_payload), file=sys.stderr)
        print(error_file, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
