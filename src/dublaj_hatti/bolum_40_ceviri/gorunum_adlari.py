# -*- coding: utf-8 -*-
from __future__ import annotations

BRIDGE_ORKESTRATORU_ADI = "bridge_motor_orkestratoru"


BRIDGE_BACKEND_ALIASES = {
    "codex": {"codex", "codex_exec", "codex-exec"},
    "gemini_flash": {"gemini_flash", "gemini-flash", "google_flash", "google-flash", "gemini_2_5_flash", "gemini_25_flash"},
    "gemini_31_flash_lite": {
        "gemini_31_flash_lite", "gemini_3_1_flash_lite_tier_1", "gemini-31-flash-lite", "gemini_3_1_flash_lite", "gemini-3.1-flash-lite", "gemini31_lite",
        "gemini", "google_ai", "google-ai", "googleai", "google",
    },
    "gemma": {"gemma", "gemma3", "gemma-3", "gemma4", "gemma_4_26b", "google_gemma", "google-gemma"},
    "groq": {"groq", "groqcloud", "groq_llama_4_scout"},
    "cerebras": {"cerebras", "cerebras_cloud", "cerebras-cloud", "cerebras_llama_3_1_8b"},
    "mistral": {"mistral", "mistralai", "mistral_ai", "mistral-ai", "mistral_nemo"},
    "claude_code": {"claude_code", "claude-code", "claude", "claude_code_cli", "claude-code-cli"},
}

BRIDGE_BACKEND_KUTU_ADLARI = {
    "codex": "llm_kopru",
    "gemini_flash": "llm_kopru",
    "gemini_31_flash_lite": "llm_kopru",
    "gemma": "llm_kopru",
    "groq": "llm_kopru",
    "cerebras": "llm_kopru",
    "mistral": "llm_kopru",
    "claude_code": "claude_code_cli",
}

FULL_TEXT_SUPPORTED_BRIDGE_BACKENDS = frozenset({"codex", "claude_code"})


class BridgeBackendSecimHatasi(ValueError):
    pass


def bridge_backend_normalize(value: str | None) -> str:
    backend = str(value or "").strip().lower()
    if not backend:
        raise BridgeBackendSecimHatasi("Bridge ceviri motoru secilmedi; varsayilan motor kullanilmaz")
    for canonical_backend, aliases in BRIDGE_BACKEND_ALIASES.items():
        if backend in aliases:
            return canonical_backend
    raise BridgeBackendSecimHatasi(f"Tanimsiz bridge ceviri motoru: {backend!r}")


def bridge_backend_kutu_adi(backend: str | None) -> str:
    return BRIDGE_BACKEND_KUTU_ADLARI[bridge_backend_normalize(backend)]


def ceviri_motoru_gorunum_adi(translator_engine: str, bridge_backend: str | None = None) -> str:
    engine = str(translator_engine or "").strip().lower()
    if engine == "codex_bridge":
        return bridge_backend_kutu_adi(bridge_backend)
    return {
        "google": "google_translate",
    }.get(engine, engine or "bilinmeyen")


def ceviri_orkestratoru_gorunum_adi(translator_engine: str) -> str:
    return BRIDGE_ORKESTRATORU_ADI if str(translator_engine or "").strip().lower() == "codex_bridge" else ""
