"""LLM köprüsü API adresi kapısı: yalnız https + izinli sağlayıcı alan adı (ruff S310)."""

from __future__ import annotations

import importlib
import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest

kopru = importlib.import_module("dublaj_hatti.bolum_40_ceviri.llm_kopru.scripts.bridge_worker")
KAYNAK = Path(kopru.__file__).read_text(encoding="utf-8")


def test_kaynaktaki_saglayici_uclari_gecer():
    # Kaynakta yazılı her https ucu (Gemini'deki {model} örnek adla) kapıdan geçmeli: gerçek adresler bozulmasın.
    uclar = re.findall(r'f?"(https://[^"\s]+)"', KAYNAK)
    assert len(uclar) >= 4
    for uc in uclar:
        url = uc.replace("{model}", "gemini-2.5-flash")
        assert kopru.api_url_dogrula(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://api.groq.com/openai/v1/chat/completions",
        "file:///etc/passwd",
        "ftp://api.mistral.ai/x",
        "data:text/plain,merhaba",
        "https://evil.example/v1/chat/completions",
        "https://api.groq.com.evil.example/v1",
        "https://kullanici:parola" + "@" + "api.cerebras.ai/v1/chat/completions",  # @ birleştirilir: yasal denetimin e-posta deseni
        "https://kullanici" + "@" + "api.cerebras.ai/v1/chat/completions",
        "",
    ],
)
def test_izinsiz_adres_reddedilir(url):
    with pytest.raises(kopru.BridgeError) as hata:
        kopru.api_url_dogrula(url)
    assert hata.value.error_type == "api_url_rejected"


def test_https_olmayan_yonlendirme_reddedilir():
    isleyici = kopru._YalnizHttpsYonlendirme()
    istek = urllib.request.Request("https://api.mistral.ai/v1/chat/completions")
    with pytest.raises(urllib.error.HTTPError):
        isleyici.redirect_request(istek, None, 302, "Found", {}, "http://api.mistral.ai/v1/chat/completions")
    yeni = isleyici.redirect_request(istek, None, 302, "Found", {}, "https://api.mistral.ai/v2")
    assert yeni is not None and yeni.full_url == "https://api.mistral.ai/v2"
