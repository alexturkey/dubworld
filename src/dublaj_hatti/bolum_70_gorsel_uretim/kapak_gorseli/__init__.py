"""Kapak görseli (isteğe bağlı): dublaj transkriptinden 9:16 kapak görselleri, kullanıcının kendi Codex CLI
oturumuyla (OpenAI hizmet şartları; transkript hizmete gönderilir, PRIVACY.md). Codex kurulu değilse atlanır.

Kullanım: `python -m dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli <transkript.txt> <çıktı klasörü>`
"""

from dublaj_hatti.bolum_70_gorsel_uretim.kapak_gorseli.codex_kapak import (  # noqa: F401
    KapakHatasi,
    codex_kurulu,
    kapak_uret,
    komut_olustur,
    sonucu_dogrula,
)
