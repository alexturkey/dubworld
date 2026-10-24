"""Ceviri arka ucu algilama.

Sira (varsayilan "auto"): Codex CLI kuruluysa codex, degilse Claude Code CLI, ikisi de yoksa yerel Opus-MT.
CLI'ler kullanicinin kendi aracidir ve kendi hesabiyla oturum acilmis olmalidir; yol PATH'ten ya da
ortam degiskeninden (CODEX_BRIDGE_CODEX_BIN / CODEX_BRIDGE_CLAUDE_CLI) bulunur.
"""

from __future__ import annotations

import os
import shutil

# Ayar değeri (transkripsiyon/çeviri kaydındaki ad) -> köprünün kanonik arka uç adı
KOPRU_ADI = {
    "codex": "codex",
    "claude_code": "claude_code",
    "gemini_2_5_flash": "gemini_flash",
    "gemini_3_1_flash_lite_tier_1": "gemini_31_flash_lite",
    "gemma_4_26b": "gemma",
    "groq_llama_4_scout": "groq",
    "cerebras_llama_3_1_8b": "cerebras",
    "mistral_nemo": "mistral",
}
LLM_ARKA_UCLARI = tuple(KOPRU_ADI)
# Gemini ailesi TEK anahtar okur (köprü yalnız CODEX_BRIDGE_GEMINI_API_KEY): eski numaralı anahtarlar eski kotayı
# sessizce devreye sokuyordu; algılama da köprüyle aynı adı arar.
# TEK KAYNAK: bu tablo köprünün (llm_kopru/scripts/bridge_worker.py *_api_key işlevleri) okuduğu adların aynısıdır;
# `dubla kontrol` (kayit.py), .env.example ve belgeler buradan beslenir. Eşitlik testi: tests/test_api_anahtar_adlari.py.
API_ANAHTARI_DEGISKENLERI = {
    "gemini_2_5_flash": ("CODEX_BRIDGE_GEMINI_API_KEY",),
    "gemini_3_1_flash_lite_tier_1": ("CODEX_BRIDGE_GEMINI_API_KEY",),
    "gemma_4_26b": ("CODEX_BRIDGE_GEMINI_API_KEY",),
    "groq_llama_4_scout": ("CODEX_BRIDGE_GROQ_API_KEY", "GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2"),
    "mistral_nemo": ("CODEX_BRIDGE_MISTRAL_API_KEY", "MISTRAL_API_KEY"),
    "cerebras_llama_3_1_8b": ("CODEX_BRIDGE_CEREBRAS_API_KEY", "CEREBRAS_API_KEY"),
}
SECENEKLER = ("auto", "yerel") + LLM_ARKA_UCLARI


class CeviriSecimHatasi(ValueError):
    pass


def cli_yolu(arka_uc: str) -> str | None:
    if arka_uc == "codex":
        ayar = os.environ.get("CODEX_BRIDGE_CODEX_BIN", "").strip()
        return ayar if ayar and os.path.isfile(ayar) else shutil.which("codex")
    if arka_uc == "claude_code":
        ayar = os.environ.get("CODEX_BRIDGE_CLAUDE_CLI", "").strip()
        return ayar if ayar and os.path.isfile(ayar) else shutil.which("claude")
    return None


def api_anahtari_var(arka_uc: str) -> bool:
    return any(os.environ.get(name, "").strip() for name in API_ANAHTARI_DEGISKENLERI.get(arka_uc, ()))


def arka_uc_durumu() -> dict[str, bool]:
    durum = {"codex": bool(cli_yolu("codex")), "claude_code": bool(cli_yolu("claude_code"))}
    for arka_uc in API_ANAHTARI_DEGISKENLERI:
        durum[arka_uc] = api_anahtari_var(arka_uc)
    durum["yerel"] = True
    return durum


def ceviri_secimi_coz(secim: str) -> dict[str, str]:
    """Kullanici secimini (translator_engine, llm_backend) ciftine cevirir."""
    value = str(secim or "auto").strip().lower()
    if value not in SECENEKLER:
        raise CeviriSecimHatasi(f"Bilinmeyen ceviri secimi: {secim!r}. Secenekler: {', '.join(SECENEKLER)}")
    if value == "auto":
        for aday in ("codex", "claude_code"):
            if cli_yolu(aday):
                return {"translator_engine": "codex_bridge", "llm_backend": aday, "kaynak": "algilandi"}
        return {"translator_engine": "yerel", "llm_backend": "", "kaynak": "yedek"}
    if value == "yerel":
        return {"translator_engine": "yerel", "llm_backend": "", "kaynak": "secildi"}
    if value in ("codex", "claude_code") and not cli_yolu(value):
        raise CeviriSecimHatasi(f"{value} CLI bulunamadi; kurup kendi hesabinizla oturum acin ya da 'yerel' secin")
    if value in API_ANAHTARI_DEGISKENLERI and not api_anahtari_var(value):
        degiskenler = " / ".join(API_ANAHTARI_DEGISKENLERI[value])
        raise CeviriSecimHatasi(f"{value} icin API anahtari yok; .env dosyasina {degiskenler} yazin")
    return {"translator_engine": "codex_bridge", "llm_backend": KOPRU_ADI[value], "kaynak": "secildi"}
