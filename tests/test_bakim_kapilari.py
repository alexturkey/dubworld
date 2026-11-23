"""Bakim turu parcalari: yerel kapilar (denetim.py, pr_kapi.py), kararli hata kodlari, ajan hizli karti ve kurulum duzeni
cumlelerinin betikle uyumu. Kart betikten kayarsa bu testler kirmizi olur. GPU yok, ag yok, indirme yok."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
SCRIPTS = KOK / "scripts"
sys.path.insert(0, str(SCRIPTS))
import denetim  # noqa: E402

POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")
WINDOWS = sys.platform == "win32" and POWERSHELL is not None


def _kos(*argv: str, girdi: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-X", "utf8", *argv], cwd=KOK, capture_output=True, timeout=120, input=girdi)


# ---------------------------------------------------------------- unicode kapisi
def test_unicode_kapisi_bidi_yakalar():
    metin = ("x = 1  # " + chr(0x202E) + "gizli\n").encode("utf-8")
    assert denetim.unicode_tara_metin("src/a.py", metin)


def test_unicode_kapisi_sifir_genislik_ve_etiket_ve_kontrol():
    assert denetim.unicode_tara_metin("docs/a.md", ("a" + chr(0x200B) + "b\n").encode("utf-8"))
    assert denetim.unicode_tara_metin("docs/a.md", ("a" + chr(0xE0041) + "b\n").encode("utf-8"))
    assert denetim.unicode_tara_metin("scripts/a.py", b"a\x00b\n")
    assert denetim.unicode_tara_metin("scripts/a.py", b"a\x1bb\n")


def test_unicode_kapisi_dile_ozgu_istisna_dar():
    zwnj = ("m" + chr(0x200C) + "n\n").encode("utf-8")
    assert not denetim.unicode_tara_metin("README.fa.md", zwnj)  # Farsca: serbest
    assert denetim.unicode_tara_metin("README.de.md", zwnj)  # baska dilde yasak
    assert denetim.unicode_tara_metin("docs/a.md", zwnj)  # README disinda yasak
    lrm = ("a" + chr(0x200E) + "b\n").encode("utf-8")
    assert not denetim.unicode_tara_metin("README.ar.md", lrm)
    assert denetim.unicode_tara_metin("README.fr.md", lrm)


def test_unicode_kapisi_dosya_basindaki_bom_serbest_ortadaki_degil():
    assert not denetim.unicode_tara_metin("scripts/kur.ps1", b"\xef\xbb\xbfWrite-Host 1\n")
    assert denetim.unicode_tara_metin("scripts/kur.ps1", b"Write-Host 1\n\xef\xbb\xbf2\n")


def test_unicode_kapisi_depo_temiz():
    durum, bulgu = denetim.kapi_unicode(KOK)
    assert durum == "GECTI", bulgu


# ---------------------------------------------------------------- denetim.py cikis kodlari (kart tablosu ile ayni)
def test_denetim_bilinmeyen_kapi_3():
    p = _kos("scripts/denetim.py", "--kapi", "yok_boyle_kapi")
    assert p.returncode == 3
    assert p.stdout.decode("utf-8", "replace").strip().splitlines()[-1].startswith("SONUC:")


def test_denetim_unicode_kapisi_0_ve_tek_sonuc_satiri():
    p = _kos("scripts/denetim.py", "--kapi", "unicode")
    assert p.returncode == 0
    satirlar = [s for s in p.stdout.decode("utf-8", "replace").splitlines() if s.startswith("SONUC:")]
    assert len(satirlar) == 1


def test_denetim_calismayan_kapi_yesil_degil(monkeypatch):
    monkeypatch.setattr(denetim, "kapilar", lambda tam: [("sahte", lambda: ("CALISMADI", ["arac yok"]))])
    assert denetim.main(["--hizli"]) == 6


def test_denetim_kirmizi_kapi_1(monkeypatch):
    monkeypatch.setattr(denetim, "kapilar", lambda tam: [("sahte", lambda: ("KIRMIZI", ["bulgu"]))])
    assert denetim.main(["--hizli"]) == 1


# ---------------------------------------------------------------- pr_kapi.py
def _yeni(yol: str, satirlar: list[str]) -> bytes:
    return ("diff --git a/%s b/%s\nnew file mode 100644\n--- /dev/null\n+++ b/%s\n@@ -0,0 +1,%d @@\n%s\n"
            % (yol, yol, yol, len(satirlar), "\n".join("+" + s for s in satirlar))).encode("utf-8")


def test_pr_kapi_ozdenetim_gecer():
    p = _kos("scripts/pr_kapi.py", "--ozdenetim")
    assert p.returncode == 0, p.stdout.decode("utf-8", "replace")


def test_pr_kapi_cikis_kodlari():
    temiz = _kos("scripts/pr_kapi.py", "--diff", "-", girdi=_yeni("docs/yeni.md", ["# Selam", "Merhaba."]))
    assert temiz.returncode == 0
    kirmizi = _kos("scripts/pr_kapi.py", "--diff", "-", girdi=_yeni(".claude/settings.json", ["{}"]))
    assert kirmizi.returncode == 1
    sari = _kos("scripts/pr_kapi.py", "--diff", "-", girdi=_yeni("src/dublaj_hatti/x.py", ['U = "https://yeni-alan.example.invalid/a"']))
    assert sari.returncode == 4
    bozuk = _kos("scripts/pr_kapi.py")
    assert bozuk.returncode == 3


def test_pr_kapi_ciktida_ham_sir_yok():
    sahte = "tok" + "en: gh" + "p_" + "A1b2C3d4" * 4 + "WxYz"
    p = _kos("scripts/pr_kapi.py", "--diff", "-", girdi=_yeni("docs/a.md", [sahte]))
    assert p.returncode == 1
    assert b"A1b2C3d4" not in p.stdout


# ---------------------------------------------------------------- kararli hata kodlari
HATA = json.loads((KOK / "docs" / "hata_imzalari.json").read_text(encoding="utf-8"))["kodlar"]


def test_hata_kodlari_benzersiz_ve_bicimli():
    kodlar = [k["kod"] for k in HATA]
    assert len(kodlar) == len(set(kodlar))
    assert all(re.fullmatch(r"DW-E-[A-Z0-9-]+", k) for k in kodlar)
    assert all(k["ilk_adim_en"] and k["ilk_adim_tr"] for k in HATA)


@pytest.mark.parametrize("kayit", HATA, ids=lambda k: k["kod"])
def test_hata_imzasi_kaynakta_gercekten_var(kayit):
    metin = (KOK / kayit["kaynak"]).read_text(encoding="utf-8-sig")
    assert kayit["imza"] in metin


@pytest.mark.parametrize("belge", ["docs/troubleshooting.md", "docs/sorun_giderme.md"])
def test_hata_belgesi_her_kodu_listeler(belge):
    metin = (KOK / belge).read_text(encoding="utf-8")
    for k in HATA:
        assert f"`{k['kod']}`" in metin, k["kod"]


# ---------------------------------------------------------------- ajan hizli karti betikle bagli
def _kart_satirlari(yarim: str) -> list[tuple[str, int, str]]:
    metin = (KOK / "AGENTS_HIZLI.md").read_text(encoding="utf-8")
    ayrac = "\n## TR\n"
    bolum = metin.split(ayrac)[0] if yarim == "EN" else metin.split(ayrac)[1]
    sonuc = []
    for satir in bolum.splitlines():
        m = re.match(r"\| `([^`]+)` \| (\d+) \| .*\| ([^|]*) \|$", satir)
        if m:
            sonuc.append((m.group(1), int(m.group(2)), m.group(3).strip()))
    return sonuc


def test_hizli_kart_en_ve_tr_ayni_kodlar():
    en, tr = _kart_satirlari("EN"), _kart_satirlari("TR")
    assert len(en) == len(tr) >= 15
    assert [(a, b) for a, b, _ in en] == [(a, b) for a, b, _ in tr]


def test_hizli_kart_kodlari_imza_dosyasinda():
    bilinen = {k["kod"] for k in HATA}
    for _, _, kodlar in _kart_satirlari("EN"):
        for kod in re.findall(r"DW-E-[A-Z0-9-]+", kodlar):
            assert kod in bilinen, kod


def test_hizli_kart_denetim_ve_pr_kapi_satirlari_betikte_tanimli():
    kart = {(a, b) for a, b, _ in _kart_satirlari("EN")}
    for kod in (0, 1, 3, 6):
        assert (r"scripts\denetim.py", kod) in kart
    for kod in (0, 1, 3, 4, 6):
        assert (r"scripts\pr_kapi.py", kod) in kart
    denetim_kaynak = (SCRIPTS / "denetim.py").read_text(encoding="utf-8")
    for kod in ("return 0", "return 1", "return 3", "return 6"):
        assert kod in denetim_kaynak


@pytest.mark.skipif(not WINDOWS, reason="kur.ps1 -Kuru yalniz Windows PowerShell ile sinanir")
def test_kur_kuru_cikis_kodlari_kartla_ayni():
    def kos(*ek: str) -> subprocess.CompletedProcess:
        return subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS / "kur.ps1"), "-Kuru", *ek],
                              capture_output=True, timeout=120, cwd=KOK)

    ok = kos("-Adim", "uv")
    assert ok.returncode == 0 and b"KURU_SONUC: HAZIR" in ok.stdout
    kotu = kos("-Adim", "yok_boyle_adim")
    assert kotu.returncode == 3 and "[DW-E-ADIM]".encode() in kotu.stdout
    lisans = kos("-Adim", "tts-xtts")
    assert "[DW-E-LISANS]".encode() in lisans.stdout and lisans.returncode in (2, 3)
    assert str(KOK).encode() not in ok.stdout  # kok yolu basilmaz (<ROOT>)


@pytest.mark.skipif(not WINDOWS, reason="kuru calisma Windows PowerShell ile sinanir")
def test_kur_kuru_hicbir_sey_yazmaz():
    onceki = sorted(p.relative_to(KOK).as_posix() for p in (KOK / "runtime_assets").rglob("*")) if (KOK / "runtime_assets").exists() else []
    subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS / "kur.ps1"), "-Kuru"],
                   capture_output=True, timeout=120, cwd=KOK)
    sonraki = sorted(p.relative_to(KOK).as_posix() for p in (KOK / "runtime_assets").rglob("*")) if (KOK / "runtime_assets").exists() else []
    assert onceki == sonraki


# ---------------------------------------------------------------- kurulum duzeni cumleleri betikle uyumlu
KUR = (SCRIPTS / "kur.ps1").read_text(encoding="utf-8-sig")


def test_kur_kalici_sistem_degisikligi_yazmaz():
    yasak = [r"\bsetx\b", r"SetEnvironmentVariable", r"Set-ItemProperty", r"New-ItemProperty", r"\$PROF" + r"ILE", r"\breg(?:\.exe)?\s+add\b",
             r"Set-Execution" + r"Policy"]
    for desen in yasak:
        assert not re.search(desen, KUR), desen


def test_kur_onbellekleri_koke_yonlendirir():
    for degisken in ("UV_CACHE_DIR", "PIP_CACHE_DIR", "$env:TMP", "$env:TEMP", "UV_NO_MODIFY_PATH"):
        assert degisken in KUR, degisken
    assert 'if (-not $env:PIP_CACHE_DIR)' in KUR  # kullanicinin kendi degeri ezilmez


def test_agents_kurulum_duzeni_cumleleri_betikte_var():
    agents = (KOK / "AGENTS.md").read_text(encoding="utf-8")
    assert "Install layout and agent discipline" in agents
    for aranan in ("UV_CACHE_DIR", "PIP_CACHE_DIR", "-Kuru"):
        assert aranan in agents and aranan in KUR, aranan
    tr = (KOK / "AGENTS.tr.md").read_text(encoding="utf-8")
    assert "Kurulum düzeni ve ajan disiplini" in tr


def test_ps1_yardimci_betikler_ascii_ve_agsiz():
    for ad in ("tani.ps1", "on_kontrol.ps1"):
        ham = (SCRIPTS / ad).read_bytes()
        ham.decode("ascii")  # PowerShell 5.1: BOM'suz ASCII disi karakter yok
        metin = ham.decode("ascii")
        for yasak in ("Invoke-WebRequest", "Invoke-RestMethod", "Start-BitsTransfer", "curl", "wget", "Out-File", "Set-Content", "Add-Content", "Remove-Item"):
            assert yasak not in metin, (ad, yasak)


# ---------------------------------------------------------------- ajan yonlendiricileri
@pytest.mark.parametrize("dosya", ["CLAUDE.md", "GEMINI.md"])
def test_yonlendirici_agents_md_e_baglanir_ve_kisa(dosya):
    metin = (KOK / dosya).read_text(encoding="utf-8")
    assert "@AGENTS.md" in metin
    assert len(metin.splitlines()) <= 15


def test_copilot_ve_aider_yonlendiricisi():
    assert "AGENTS.md" in (KOK / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in (KOK / ".aider.conf.yml").read_text(encoding="utf-8")


def test_issue_formlari_bos_issue_kapali_ve_guvenlik_baglantisi():
    metin = (KOK / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in metin
    assert "security/advisories" in metin


# ---------------------------------------------------------------- repo_kapi.json kaydi betikle ayni
def test_repo_kapi_kaydi_betiklerle_ayni():
    import pr_kombinasyon

    ayar = json.loads((SCRIPTS / "repo_kapi.json").read_text(encoding="utf-8"))
    assert ayar["kit_surumu"] == 2 and ayar["repo"]["ad"] == "DubWorld"
    assert sorted(pr_kombinasyon.HOST_IZIN) == ayar["izinli_alan_adlari"]
    assert ayar["hata"]["kod_oneki"] == "DW"
    kart = {(a, b) for a, b, _ in _kart_satirlari("EN")}
    for betik, kodlar in ayar["cikis_kodlari"].items():
        kart_adi = "scripts\\" + betik
        for kod in kodlar:
            assert (kart_adi, int(kod)) in kart, (kart_adi, kod)
