from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
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
        return
    # POSIX: agacli_calistir alt sureci kendi oturum/surec grubunda baslatir (start_new_session); proc.kill()
    # yalniz grubun basini oldurur, torunlar (CLI'nin arac surecleri) init'e devredilip acik kalir. Grubun
    # tamami once SIGTERM, kisa beklemeden sonra SIGKILL alir. Grup bizimkiyle ayniysa (cagiran
    # start_new_session=False verdiyse) kendimizi oldurmemek icin yalniz proc.kill().
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    if pgid == os.getpgrp():
        proc.kill()
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def agacli_calistir(command: list[str], *, input_text: str, timeout: int, **kwargs: Any) -> subprocess.CompletedProcess:
    """subprocess.run(capture_output=True, text=True) eşdeğeri; zaman aşımında süreç ağacını kapatır."""
    if os.name != "nt":
        kwargs.setdefault("start_new_session", True)
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
BACKEND_NAME = "claude_code"
BACKEND_BOX_NAME = "claude_code_cli"
RUNTIME_ROOT = BRIDGE_ROOT / "runtime"
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
BACKEND_CONFIG_FILE = BRIDGE_ROOT / "backends" / BACKEND_BOX_NAME / "backend_config.json"
DEFAULT_SCHEMA_FILE = BRIDGE_ROOT / "backends" / BACKEND_BOX_NAME / "output_schema.json"
CLAUDE_WORK_DIR = Path(tempfile.gettempdir()) / "dublaj_hatti_claude_code_cli"

MAX_CONTRACT_RETRIES = 2
MAX_NATURAL_BLOCKS_CHAIN_REVIEW_RETRIES = 1
MAX_JOB_ID_MISMATCH_RETRIES = 1
MAX_FULL_TEXT_PARTIAL_RETRIES = 2
MAX_ACCEPTED_CANDIDATES = 10
DEFAULT_CANDIDATE_COUNT = 7
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"
DEFAULT_CLAUDE_EFFORT = "medium"
VALID_CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
FULL_TEXT_HIGH_EFFORT_WORD_THRESHOLD = 6000
DEFAULT_TIMING_REPAIR_TIMEOUT_SECONDS = 45
BRIDGE_ERROR_MARKER = "CODEX_BRIDGE_ERROR"
TOKEN_USAGE_SOURCE = "claude_code_cli_result_envelope"
PRICING_STATUS_UNVERIFIED = "unverified_local_price_table"

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

OUTPUT_DISCIPLINE_PROMPT = """CIKTI DISIPLINI:
- Yalniz tek bir JSON nesnesi dondur. Aciklama, selamlama, markdown basligi veya kod citasi disinda metin yazma.
- JSON asagidaki semaya birebir uymalidir; sema disinda alan ekleme.
- job_id degerini job icindeki deger ile ayni yaz.
- Arac cagirma, dosya okuma veya yazma girisiminde bulunma; gorev yalniz metin uretmektir."""


class BridgeError(RuntimeError):
    def __init__(
        self,
        message: str,
        error_type: str = "bridge_error",
        retryable: bool = False,
        retry_after_at: str = "",
        retry_after_seconds: int = 0,
        retry_reason: str = "",
    ):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.retry_after_at = retry_after_at
        self.retry_after_seconds = retry_after_seconds
        self.retry_reason = retry_reason


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def ensure_dirs() -> None:
    for directory in (INBOX_DIR, PROCESSING_DIR, OUTBOX_DIR, FAILED_DIR, LOGS_DIR, TMP_DIR, USAGE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload.setdefault("timestamp", now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_") or "job"


def estimate_text_tokens(text: str) -> int:
    return max(1, len(str(text or "")) // 4)


def format_bridge_error(message: str, details: dict[str, Any]) -> str:
    return f"{BRIDGE_ERROR_MARKER} {json.dumps({'message': message, **details}, ensure_ascii=False)}"


def backend_config() -> dict[str, Any]:
    return read_json(BACKEND_CONFIG_FILE)


def claude_model() -> str:
    config = backend_config()
    default_model = str(config.get("default_model") or DEFAULT_CLAUDE_MODEL)
    model = os.getenv(str(config.get("model_env") or "CODEX_BRIDGE_CLAUDE_MODEL"), default_model).strip()
    return model or default_model


def full_text_source_word_count(job: dict[str, Any] | None) -> int:
    if not isinstance(job, dict) or job.get("task_type") != "full_text_translation":
        return 0
    return len(str(job.get("source_text") or "").split())


def claude_effort(job: dict[str, Any] | None = None) -> str:
    config = backend_config()
    threshold = int(config.get("full_text_high_effort_word_threshold") or FULL_TEXT_HIGH_EFFORT_WORD_THRESHOLD)
    if full_text_source_word_count(job) > threshold:
        high_effort = str(config.get("full_text_high_effort") or "high").strip().lower()
        if high_effort in VALID_CLAUDE_EFFORTS:
            return high_effort
    default_effort = str(config.get("default_effort") or DEFAULT_CLAUDE_EFFORT).strip().lower()
    effort = os.getenv(str(config.get("effort_env") or "CODEX_BRIDGE_CLAUDE_EFFORT"), default_effort).strip().lower()
    if effort in VALID_CLAUDE_EFFORTS:
        return effort
    return default_effort if default_effort in VALID_CLAUDE_EFFORTS else DEFAULT_CLAUDE_EFFORT


def prompt_mode(job: dict[str, Any] | None) -> str:
    if not isinstance(job, dict):
        return ""
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    return str(options.get("prompt_mode") or "").strip()


def voice_engine(job: dict[str, Any] | None) -> str:
    if not isinstance(job, dict):
        return ""
    voice = job.get("voice") if isinstance(job.get("voice"), dict) else {}
    return str(voice.get("engine") or "").strip().lower()


def backend_asset_path(relative_path: str) -> Path:
    return BRIDGE_ROOT / "backends" / BACKEND_BOX_NAME / relative_path


def prompt_file_for_job(job: dict[str, Any] | None) -> Path:
    config = backend_config()
    prompt_files = config.get("prompt_files") if isinstance(config.get("prompt_files"), dict) else {}
    mode = prompt_mode(job)
    if mode and mode in prompt_files:
        return backend_asset_path(str(prompt_files[mode]))
    if job is not None and job.get("task_type") == "full_text_translation":
        if "full_text_translation" in prompt_files:
            return backend_asset_path(str(prompt_files["full_text_translation"]))
    engine = voice_engine(job)
    engine_key = {
        "supertonic": "supertonic_tts",
        "supertonic_tts": "supertonic_tts",
        "voxcpm2": "voxcpm2_tts",
        "voxcpm2_tts": "voxcpm2_tts",
    }.get(engine, "")
    if engine_key and engine_key in prompt_files:
        return backend_asset_path(str(prompt_files[engine_key]))
    return backend_asset_path(str(prompt_files.get("default") or "prompts/supertonic.md"))


def output_schema_file_for_job(job: dict[str, Any] | None) -> Path:
    config = backend_config()
    schemas = config.get("output_schemas") if isinstance(config.get("output_schemas"), dict) else {}
    mode = prompt_mode(job)
    if mode and mode in schemas:
        return backend_asset_path(str(schemas[mode]))
    if job is not None and job.get("task_type") == "full_text_translation":
        if "full_text_translation" in schemas:
            return backend_asset_path(str(schemas["full_text_translation"]))
    default_schema = str(schemas.get("default") or config.get("output_schema") or "output_schema.json")
    return backend_asset_path(default_schema)


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


def discourse_context_payload(job: dict[str, Any]) -> dict[str, Any]:
    discourse_segments = job.get("discourse_segments")
    segments = job.get("segments") if isinstance(job.get("segments"), list) else []
    main_ids = [str(segment.get("id")) for segment in segments if isinstance(segment, dict)]
    if not isinstance(discourse_segments, list) or not discourse_segments:
        ordered_source_text = " ".join(
            str(segment.get("text") or "").strip()
            for segment in segments
            if isinstance(segment, dict)
        ).strip()
        return {
            "ordered_source_text": ordered_source_text,
            "main_segment_ids": main_ids,
            "context_before": [],
            "context_after": [],
        }
    ordered_items = []
    for item in discourse_segments:
        if not isinstance(item, dict):
            continue
        ordered_items.append({"id": str(item.get("id")), "text": str(item.get("text") or "").strip()})
    main_id_set = set(main_ids)
    first_main_index = next((index for index, item in enumerate(ordered_items) if item["id"] in main_id_set), 0)
    last_main_index = next(
        (index for index in range(len(ordered_items) - 1, -1, -1) if ordered_items[index]["id"] in main_id_set),
        len(ordered_items) - 1,
    )
    return {
        "ordered_source_text": " ".join(item["text"] for item in ordered_items if item["text"]).strip(),
        "main_segment_ids": main_ids,
        "context_before": ordered_items[:first_main_index],
        "context_after": ordered_items[last_main_index + 1:],
    }


def prompt_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in job.items() if not str(key).startswith("_")}
    payload.pop("discourse_segments", None)
    if job.get("task_type") != "full_text_translation":
        payload["discourse_context"] = discourse_context_payload(job)
    return payload


def build_system_prompt(job: dict[str, Any]) -> str:
    target_lang = hedef_dil.is_hedef_dili(job)
    mode_prompt = hedef_dil.istem_isle(prompt_file_for_job(job).read_text(encoding="utf-8"), target_lang)
    schema_text = hedef_dil.yer_tutuculari_doldur(output_schema_file_for_job(job).read_text(encoding="utf-8"), target_lang)
    return "\n\n".join(
        [
            mode_prompt.strip(),
            ASR_CONTEXTUAL_CORRECTION_PROMPT,
            VERI_TALIMAT_AYRIMI,
            OUTPUT_DISCIPLINE_PROMPT,
            "ZORUNLU JSON SEMASI:",
            schema_text.strip(),
        ]
    )


def build_stdin_payload(job: dict[str, Any]) -> str:
    return "JOB JSON:\n" + json.dumps(prompt_job_payload(job), ensure_ascii=False, indent=2)


def claude_executable() -> list[str]:
    explicit = os.getenv("CODEX_BRIDGE_CLAUDE_CLI", "").strip()
    if explicit:
        return [explicit]
    # Tam yol zorunlu: "cmd /c claude" calisma dizinindeki claude.bat'i once bulabilirdi (GUV-11).
    resolved = shutil.which("claude")
    if resolved:
        return [resolved]
    raise BridgeError(
        "Claude Code CLI bulunamadi (PATH'te 'claude' yok). Kurun ya da CODEX_BRIDGE_CLAUDE_CLI ile tam yolu verin.",
        error_type="claude_cli_missing",
    )


def claude_work_dir() -> Path:
    CLAUDE_WORK_DIR.mkdir(parents=True, exist_ok=True)
    return CLAUDE_WORK_DIR.resolve()


def build_claude_command(system_prompt_file: Path, job: dict[str, Any] | None = None) -> list[str]:
    return [
        *claude_executable(),
        "--print",
        "--output-format",
        "json",
        "--model",
        claude_model(),
        "--effort",
        claude_effort(job),
        "--system-prompt-file",
        str(system_prompt_file),
        "--disallowed-tools",
        "*",
        "--strict-mcp-config",
        "--no-chrome",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--setting-sources",
        "",
    ]


def is_timing_repair_job(job: dict[str, Any]) -> bool:
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    return bool(options.get("timing_repair") or options.get("repair_round"))


def timing_repair_timeout_seconds(job: dict[str, Any], timeout_seconds: int) -> int:
    if not is_timing_repair_job(job):
        return timeout_seconds
    try:
        configured = int(os.getenv("CODEX_BRIDGE_TIMING_REPAIR_TIMEOUT_SECONDS", "").strip() or DEFAULT_TIMING_REPAIR_TIMEOUT_SECONDS)
    except ValueError:
        configured = DEFAULT_TIMING_REPAIR_TIMEOUT_SECONDS
    return max(1, min(timeout_seconds, configured))


HTTP_STATUS_PATTERN = r"(?:api error|status(?: code)?|http)[:\s]*"
CLAUDE_ERROR_RULES = (
    (
        re.compile(r"not logged in|please run /login|invalid api key|authentication_error|oauth token (?:has )?expired"),
        {"error_type": "claude_not_authenticated", "retryable": False, "retry_after_seconds": 0, "retry_reason": "not_logged_in"},
    ),
    (
        re.compile(r"usage limit|rate[_ ]limit(?:_error|ed)?\b|" + HTTP_STATUS_PATTERN + r"429\b"),
        {"error_type": "claude_usage_limit", "retryable": True, "retry_after_seconds": 900, "retry_reason": "usage_limit"},
    ),
    (
        re.compile(r"overloaded(?:_error)?\b|" + HTTP_STATUS_PATTERN + r"529\b"),
        {"error_type": "claude_overloaded", "retryable": True, "retry_after_seconds": 120, "retry_reason": "overloaded"},
    ),
    (
        re.compile(r"\b(?:econnreset|etimedout|enotfound|econnrefused|eai_again)\b|socket hang up|fetch failed|network error"),
        {"error_type": "claude_temporary_network", "retryable": True, "retry_after_seconds": 120, "retry_reason": "network"},
    ),
    (
        re.compile(r"\bapi_error\b|internal server error|" + HTTP_STATUS_PATTERN + r"5\d\d\b"),
        {"error_type": "claude_api_error", "retryable": True, "retry_after_seconds": 120, "retry_reason": "api_error"},
    ),
)


def classify_claude_error(result_text: str, stderr_text: str, terminal_reason: str) -> dict[str, Any]:
    combined = "\n".join((result_text, stderr_text, terminal_reason)).lower()
    for pattern, details in CLAUDE_ERROR_RULES:
        if pattern.search(combined):
            return dict(details)
    return {
        "error_type": "claude_cli_error",
        "retryable": False,
        "retry_after_seconds": 0,
        "retry_reason": "",
    }


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = str(text or "").strip()
    if not candidate:
        raise BridgeError("Claude Code CLI bos cevap dondurdu", error_type="claude_empty_result")
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", candidate, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    start = candidate.find("{")
    if start == -1:
        raise BridgeError("Claude Code CLI cevabinda JSON bulunamadi", error_type="claude_result_not_json")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(candidate)):
        character = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(candidate[start:index + 1])
                except json.JSONDecodeError as exc:
                    raise BridgeError(
                        f"Claude Code CLI JSON parse edilemedi: {exc}",
                        error_type="claude_result_not_json",
                    ) from exc
    raise BridgeError("Claude Code CLI cevabinda kapanmamis JSON var", error_type="claude_result_not_json")


def record_api_usage(event: dict[str, Any]) -> None:
    append_jsonl(API_USAGE_EVENTS_FILE, event)
    summary: dict[str, Any] = {}
    if API_USAGE_SUMMARY_FILE.exists():
        try:
            summary = read_json(API_USAGE_SUMMARY_FILE)
        except Exception:
            summary = {}
    models = summary.get("models") if isinstance(summary.get("models"), dict) else {}
    model_key = str(event.get("model") or "unknown")
    bucket = models.get(model_key) if isinstance(models.get(model_key), dict) else {
        "request_count": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "duration_seconds": 0.0,
    }
    bucket["request_count"] = int(bucket.get("request_count") or 0) + 1
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
        bucket[field] = int(bucket.get(field) or 0) + int(event.get(field) or 0)
    bucket["duration_seconds"] = round(float(bucket.get("duration_seconds") or 0.0) + float(event.get("duration_seconds") or 0.0), 3)
    models[model_key] = bucket
    summary["backend"] = BACKEND_NAME
    summary["models"] = models
    summary["updated_at"] = now_iso()
    write_json(API_USAGE_SUMMARY_FILE, summary)


def run_claude_model(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_dirs()
    system_prompt = build_system_prompt(job)
    stdin_payload = build_stdin_payload(job)
    job_id = safe_name(str(job.get("job_id") or "job"))
    system_prompt_file = TMP_DIR / f"{job_id}_{int(time.time() * 1000)}_system_prompt.md"
    system_prompt_file.write_text(system_prompt, encoding="utf-8")
    command = build_claude_command(system_prompt_file, job)
    effective_timeout = timing_repair_timeout_seconds(job, timeout_seconds)
    work_dir = claude_work_dir()
    started = time.time()
    try:
        effective_timeout = kalan_sure(effective_timeout)
        completed = agacli_calistir(
            command,
            input_text=stdin_payload,
            timeout=effective_timeout,
            cwd=str(work_dir),
            creationflags=NO_WINDOW_FLAGS,
        )
    except subprocess.TimeoutExpired as exc:
        raise BridgeError(
            f"Claude Code CLI timeout: {effective_timeout}s",
            error_type="claude_timeout",
            retryable=True,
            retry_after_seconds=300,
            retry_reason="worker_timeout",
        ) from exc
    finally:
        system_prompt_file.unlink(missing_ok=True)
    duration_seconds = round(time.time() - started, 3)
    stderr_text = completed.stderr or ""
    stdout_text = completed.stdout or ""
    (LOGS_DIR / f"{job_id}_claude_stderr.txt").write_text(stderr_text, encoding="utf-8")

    if completed.returncode != 0 and not stdout_text.strip():
        details = classify_claude_error("", stderr_text, "")
        raise BridgeError(
            f"Claude Code CLI basarisiz oldu: returncode={completed.returncode} {stderr_text.strip()[:400]}",
            **details,
        )
    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        raise BridgeError(
            f"Claude Code CLI zarfi JSON degil: {exc}",
            error_type="claude_envelope_not_json",
            retryable=True,
            retry_after_seconds=60,
            retry_reason="envelope_parse",
        ) from exc
    if not isinstance(envelope, dict):
        raise BridgeError("Claude Code CLI zarfi object olmali", error_type="claude_envelope_not_json")

    result_text = str(envelope.get("result") or "")
    terminal_reason = str(envelope.get("terminal_reason") or "")
    if envelope.get("is_error"):
        details = classify_claude_error(result_text, stderr_text, terminal_reason)
        raise BridgeError(
            f"Claude Code CLI hata dondurdu: {result_text.strip()[:400]}",
            **details,
        )

    usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
    output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
    model_usage = envelope.get("modelUsage") if isinstance(envelope.get("modelUsage"), dict) else {}
    reported_model = next(iter(model_usage), "") if model_usage else ""
    input_tokens = int(usage.get("input_tokens") or 0)
    cached_input_tokens = int(usage.get("cache_read_input_tokens") or 0)
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    reasoning_output_tokens = int(output_details.get("thinking_tokens") or 0)

    meta = {
        "backend": BACKEND_NAME,
        "backend_box": BACKEND_BOX_NAME,
        "execution_mode": "claude_code_cli",
        "model": reported_model or claude_model(),
        "requested_model": claude_model(),
        "reasoning_effort": claude_effort(job),
        "duration_seconds": duration_seconds,
        "estimated_input_tokens": estimate_text_tokens(system_prompt) + estimate_text_tokens(stdin_payload),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": input_tokens + cached_input_tokens + cache_creation_input_tokens + output_tokens,
        "token_usage_available": bool(usage),
        "token_usage_source": TOKEN_USAGE_SOURCE,
        "pricing_status": PRICING_STATUS_UNVERIFIED,
        "prompt_mode": prompt_mode(job),
        "prompt_file": str(prompt_file_for_job(job)),
        "output_schema_file": str(output_schema_file_for_job(job)),
        "work_dir": str(work_dir),
        "usage_metadata": {
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "reported_cost_usd": envelope.get("total_cost_usd"),
            "session_id": envelope.get("session_id"),
            "service_tier": usage.get("service_tier"),
            "num_turns": envelope.get("num_turns"),
            "terminal_reason": terminal_reason,
            "cli_duration_ms": envelope.get("duration_ms"),
        },
        "rate_limit_headers": {},
    }
    record_api_usage({
        "event": "claude_request",
        "job_id": str(job.get("job_id") or ""),
        "model": meta["model"],
        "reasoning_effort": meta["reasoning_effort"],
        "duration_seconds": duration_seconds,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": meta["total_tokens"],
        "reported_cost_usd": envelope.get("total_cost_usd"),
    })
    result = extract_json_object(result_text)
    return result, meta


def expected_segment_ids(job: dict[str, Any]) -> list[str]:
    return [str(segment["id"]) for segment in job.get("segments", []) if isinstance(segment, dict)]


def normalized_candidate_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().strip(" .,!?:;"))


def normalize_result_candidates(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    expected_count = candidate_count(job)
    normalizations: list[dict[str, Any]] = []
    translations = result.get("translations")
    if not isinstance(translations, list):
        return normalizations
    for item in translations:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list):
            continue
        cleaned: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            key = normalized_candidate_key(text)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        trimmed = cleaned[:MAX_ACCEPTED_CANDIDATES]
        if trimmed != candidates:
            normalizations.append({
                "id": str(item.get("id")),
                "received_count": len(candidates),
                "kept_count": len(trimmed),
                "expected_count": expected_count,
            })
        item["candidates"] = trimmed
    return normalizations


def normalize_kept_terms_to_spoken_candidates(result: dict[str, Any]) -> list[dict[str, Any]]:
    normalizations: list[dict[str, Any]] = []
    translations = result.get("translations")
    if not isinstance(translations, list):
        return normalizations
    for item in translations:
        if not isinstance(item, dict):
            continue
        kept_terms = item.get("kept_terms")
        if not isinstance(kept_terms, list):
            item["kept_terms"] = []
            normalizations.append({"id": str(item.get("id")), "reason": "missing_kept_terms"})
            continue
        cleaned = []
        for term in kept_terms:
            if not isinstance(term, dict):
                continue
            text = str(term.get("text") or "").strip()
            if not text:
                continue
            cleaned.append({
                "text": text,
                "reason": str(term.get("reason") or "unspecified"),
                "confidence": float(term.get("confidence") or 0.0),
            })
        if cleaned != kept_terms:
            normalizations.append({"id": str(item.get("id")), "reason": "kept_terms_normalized"})
        item["kept_terms"] = cleaned
    return normalizations


def missing_segment_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    translations = result.get("translations") if isinstance(result.get("translations"), list) else []
    seen = {str(item.get("id")) for item in translations if isinstance(item, dict)}
    return [{"id": segment_id, "reason": "missing_segment"} for segment_id in expected_segment_ids(job) if segment_id not in seen]


def empty_candidate_violations(result: dict[str, Any]) -> list[dict[str, Any]]:
    violations = []
    translations = result.get("translations") if isinstance(result.get("translations"), list) else []
    for item in translations:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not [text for text in candidates if str(text or "").strip()]:
            violations.append({"id": str(item.get("id")), "reason": "empty_candidates"})
    return violations


def candidate_word_count(value: str, target_lang: str = "") -> int:
    def sayac(metin: str) -> int:
        return len([word for word in re.split(r"\s+", str(metin or "").strip()) if word])

    return hedef_dil.kelime_esdegeri(value, target_lang or "tr", sayac)


def segment_contract_minimum(segment: dict[str, Any]) -> int:
    for key in ("hard_minimum_word_count", "invalid_if_below_word_count", "repair_minimum_word_count"):
        value = segment.get(key)
        if isinstance(value, (int, float)) and int(value) > 0:
            return int(value)
    timing_contract = segment.get("timing_contract")
    if isinstance(timing_contract, dict):
        value = timing_contract.get("minimum_word_count")
        if isinstance(value, (int, float)) and int(value) > 0:
            return int(value)
    return 0


def timing_contract_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    target_lang = hedef_dil.is_hedef_dili(job)
    minimums = {
        str(segment.get("id")): segment_contract_minimum(segment)
        for segment in job.get("segments", [])
        if isinstance(segment, dict)
    }
    violations = []
    translations = result.get("translations") if isinstance(result.get("translations"), list) else []
    for item in translations:
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("id"))
        minimum = minimums.get(segment_id, 0)
        if minimum <= 0:
            continue
        candidates = item.get("candidates") if isinstance(item.get("candidates"), list) else []
        if candidates and all(candidate_word_count(text, target_lang) < minimum for text in candidates):
            violations.append({"id": segment_id, "reason": "below_timing_minimum", "minimum_word_count": minimum})
    return violations


def candidate_count_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    expected_count = candidate_count(job)
    violations = []
    translations = result.get("translations") if isinstance(result.get("translations"), list) else []
    for item in translations:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates") if isinstance(item.get("candidates"), list) else []
        if len(candidates) < expected_count:
            violations.append({
                "id": str(item.get("id")),
                "reason": "candidate_count_below_expected",
                "expected_count": expected_count,
                "received_count": len(candidates),
            })
    return violations


def repair_violations(job: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    return missing_segment_violations(job, result) + empty_candidate_violations(result)


def build_contract_retry_job(job: dict[str, Any], violations: list[dict[str, Any]], attempt: int) -> dict[str, Any]:
    violation_ids = {str(item["id"]) for item in violations}
    retry_job = {key: value for key, value in job.items() if not str(key).startswith("_")}
    retry_job["segments"] = [
        segment for segment in job.get("segments", [])
        if isinstance(segment, dict) and str(segment.get("id")) in violation_ids
    ]
    retry_job["job_id"] = f"{job.get('job_id')}_contract_retry_{attempt}"
    options = dict(retry_job.get("options") or {})
    options["contract_retry_attempt"] = attempt
    options["contract_retry_reasons"] = sorted({str(item.get("reason") or "") for item in violations})
    retry_job["options"] = options
    return retry_job


def merge_retry_result(result: dict[str, Any], retry_result: dict[str, Any]) -> dict[str, Any]:
    translations = result.get("translations") if isinstance(result.get("translations"), list) else []
    retry_translations = retry_result.get("translations") if isinstance(retry_result.get("translations"), list) else []
    by_id = {str(item.get("id")): item for item in translations if isinstance(item, dict)}
    for item in retry_translations:
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or not [text for text in candidates if str(text or "").strip()]:
            continue
        by_id[str(item.get("id"))] = item
    result["translations"] = list(by_id.values())
    return result


def full_text_target_review_violations(result: dict[str, Any]) -> list[str]:
    violations = []
    translated_text = str(result.get("translated_text") or "")
    if re.search(r"\?\s+[a-zçğıöşü]", translated_text):
        violations.append("question_mark_followed_by_lowercase_clause")
    return violations


def build_full_text_review_retry_job(job: dict[str, Any], review_violations: list[str]) -> dict[str, Any]:
    retry_job = {key: value for key, value in job.items() if not str(key).startswith("_")}
    options = dict(retry_job.get("options") or {})
    options["full_text_review_violations"] = review_violations
    retry_job["options"] = options
    return retry_job


def validate_result(job: dict[str, Any], result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise BridgeError("Result JSON object olmali")
    if str(result.get("job_id") or "") != str(job.get("job_id") or ""):
        raise BridgeError(
            "Result job_id job ile eslesmiyor",
            error_type="translation_result_job_id_mismatch",
            retryable=True,
            retry_reason="job_id_mismatch",
        )
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
        if result.get("status") == "success":
            translated_text = result.get("translated_text")
            if not isinstance(translated_text, str) or not translated_text.strip():
                raise BridgeError("Full metin success result translated_text icermeli")
            integrity = result.get("integrity")
            if not isinstance(integrity, dict):
                raise BridgeError("Full metin success result integrity icermeli")
            if integrity.get("source_coverage") != "complete":
                raise BridgeError("Full metin success result tam kaynak kapsami beyan etmeli")
            if integrity.get("omitted_source_content") or integrity.get("added_content"):
                raise BridgeError("Full metin success result eksiltme veya ekleme beyan ediyor")
            review_violations = full_text_target_review_violations(result)
            if review_violations:
                raise BridgeError("Full metin cevirisi supheli cumle siniri iceriyor: " + "; ".join(review_violations))
        return
    translations = result.get("translations")
    if not isinstance(translations, list):
        raise BridgeError("Result translations liste olmali")
    expected = set(expected_segment_ids(job))
    seen = {str(item.get("id")) for item in translations if isinstance(item, dict)}
    unexpected = seen - expected
    if unexpected:
        raise BridgeError(f"Result beklenmeyen segment id iceriyor: {sorted(unexpected)}")
    missing = expected - seen
    if missing:
        raise BridgeError(
            f"Result eksik segment iceriyor: {sorted(missing)}",
            error_type="translation_result_incomplete",
            retryable=True,
            retry_reason="missing_segment_ids",
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


def run_natural_blocks_with_chain_review(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    result, meta = run_claude_model(job, timeout_seconds)
    review_runs = []
    for attempt in range(1, MAX_NATURAL_BLOCKS_CHAIN_REVIEW_RETRIES + 1):
        violations = natural_blocks_review_violations(job, result)
        if not violations:
            break
        retry_job = build_natural_blocks_review_retry_job(job, result, violations, attempt)
        if not retry_job.get("segments"):
            break
        retry_result, retry_meta = run_claude_model(retry_job, timeout_seconds)
        result = replace_natural_blocks_retry_result(result, retry_result)
        review_runs.append({
            "attempt": attempt,
            "violation_count": len(violations),
            "segment_ids": [str(item.get("id")) for item in violations],
            "meta": retry_meta,
        })
    meta["natural_blocks_chain_review"] = {
        "attempts": len(review_runs),
        "remaining_violation_count": len(natural_blocks_review_violations(job, result)),
        "runs": review_runs,
    }
    return result, meta


def run_claude_with_contract_retry(job: dict[str, Any], timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if is_natural_blocks_job(job):
        return run_natural_blocks_with_chain_review(job, timeout_seconds)
    result, meta = run_claude_model(job, timeout_seconds)
    if job.get("task_type") == "full_text_translation":
        initial_status = str(result.get("status") or "")
        retry_runs = []
        for attempt in range(1, MAX_FULL_TEXT_PARTIAL_RETRIES + 1):
            review_violations = full_text_target_review_violations(result)
            if result.get("status") != "partial" and not review_violations:
                break
            retry_job = build_full_text_review_retry_job(job, review_violations)
            previous_status = str(result.get("status") or "")
            result, one_meta = run_claude_model(retry_job, timeout_seconds)
            retry_runs.append({
                "attempt": attempt,
                "previous_status": previous_status,
                "review_violations": review_violations,
                "returned_status": str(result.get("status") or ""),
                "meta": one_meta,
            })
        meta["contract_retry"] = {
            "attempts": len(retry_runs),
            "mode": "full_text_translation",
            "initial_status": initial_status,
            "final_status": str(result.get("status") or ""),
            "runs": retry_runs,
        }
        return result, meta

    job_id_runs = []
    for attempt in range(1, MAX_JOB_ID_MISMATCH_RETRIES + 1):
        if str(result.get("job_id") or "") == str(job.get("job_id") or ""):
            break
        returned_job_id = str(result.get("job_id") or "")
        result, retry_meta = run_claude_model(job, timeout_seconds)
        job_id_runs.append({"attempt": attempt, "returned_job_id": returned_job_id, "meta": retry_meta})
    meta["job_id_mismatch_retry"] = {
        "attempts": len(job_id_runs),
        "matched": str(result.get("job_id") or "") == str(job.get("job_id") or ""),
        "runs": job_id_runs,
    }

    retry_runs = []
    for attempt in range(1, MAX_CONTRACT_RETRIES + 1):
        violations = repair_violations(job, result)
        if not violations:
            break
        retry_job = build_contract_retry_job(job, violations, attempt)
        if not retry_job.get("segments"):
            break
        retry_result, one_meta = run_claude_model(retry_job, timeout_seconds)
        retry_result["job_id"] = job.get("job_id")
        result = merge_retry_result(result, retry_result)
        retry_runs.append({
            "attempt": attempt,
            "violation_count": len(violations),
            "segment_ids": [str(item.get("id")) for item in violations],
            "meta": one_meta,
        })
    remaining = repair_violations(job, result)
    timing_advisories = timing_contract_violations(job, result)
    remaining_candidate_count = candidate_count_violations(job, result)
    meta["contract_retry"] = {
        "attempts": len(retry_runs),
        "remaining_violation_count": len(remaining),
        "remaining_segment_ids": [str(item.get("id")) for item in remaining],
        "remaining_candidate_count_violation_count": len(remaining_candidate_count),
        "remaining_candidate_count_segment_ids": [str(item.get("id")) for item in remaining_candidate_count],
        "timing_advisory_violation_count": len(timing_advisories),
        "timing_advisory_segment_ids": [str(item.get("id")) for item in timing_advisories],
        "runs": retry_runs,
    }
    return result, meta


def run_mock(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("task_type") == "full_text_translation":
        return {
            "job_id": job.get("job_id"),
            "status": "success",
            "translated_text": f"[mock] {job.get('source_text')}",
            "integrity": {
                "source_coverage": "complete",
                "omitted_source_content": False,
                "added_content": False,
            },
        }
    expected_count = candidate_count(job)
    return {
        "job_id": job.get("job_id"),
        "status": "success",
        "translations": [
            {
                "id": str(segment.get("id")),
                "candidates": [f"[mock {index + 1}] {segment.get('text')}" for index in range(expected_count)],
                "kept_terms": [],
            }
            for segment in job.get("segments", [])
            if isinstance(segment, dict)
        ],
    }


def acquire_job() -> Path | None:
    ensure_dirs()
    jobs = sorted(path for path in INBOX_DIR.glob("*.json") if path.is_file())
    if not jobs:
        return None
    job_file = jobs[0]
    target = PROCESSING_DIR / job_file.name
    shutil.move(str(job_file), str(target))
    return target


def write_status(job_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"job_id": job_id, "status": status, "updated_at": now_iso(), "backend": BACKEND_NAME}
    if extra:
        payload.update(extra)
    write_json(WORK_ROOT / "status.json", payload)


def process_job(job_file: Path, mock: bool, timeout_seconds: int, keep_job: bool = False) -> Path:
    job = read_json(job_file)
    job["_job_file"] = str(job_file)
    validate_job(job)
    job_id = safe_name(str(job["job_id"]))
    log_file = LOGS_DIR / f"{job_id}.jsonl"
    selected_model = claude_model() if not mock else "mock"
    append_jsonl(log_file, {
        "event": "started",
        "job_file": str(job_file),
        "mock": mock,
        "backend": BACKEND_NAME if not mock else "mock",
        "model": selected_model,
    })
    write_status(str(job["job_id"]), "processing", {"mock": mock, "model": selected_model})

    if mock:
        result = run_mock(job)
        meta = {"mode": "mock", "backend": BACKEND_NAME, "execution_mode": "mock"}
    else:
        result, meta = run_claude_with_contract_retry(job, timeout_seconds)

    if job.get("task_type") != "full_text_translation":
        candidate_normalizations = normalize_result_candidates(job, result)
        if candidate_normalizations:
            meta["candidate_normalizations"] = candidate_normalizations
        kept_terms_normalizations = normalize_kept_terms_to_spoken_candidates(result)
        if kept_terms_normalizations:
            meta["kept_terms_spoken_normalizations"] = kept_terms_normalizations
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
        pass
    error_file = FAILED_DIR / f"{job_id}_error.json"
    payload = {
        "job_id": job_id,
        "status": "failed",
        "backend": BACKEND_NAME,
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
    parser = argparse.ArgumentParser(description="Claude Code CLI ceviri motoru worker")
    parser.add_argument("--mock", action="store_true", help="Claude Code CLI cagirmadan deterministik test sonucu uret")
    parser.add_argument("--timeout", type=int, default=900, help="Claude Code CLI timeout saniye")
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
            "backend": BACKEND_NAME,
            "backend_box": BACKEND_BOX_NAME,
        }
        print(format_bridge_error(str(exc), error_payload), file=sys.stderr)
        print(error_file, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
