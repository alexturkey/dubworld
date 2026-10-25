"""Web arayüzü (tek arayüz) ve masaüstü penceresi: göz dostu renkler kontrast ölçüsünü geçer (gündüz ve gece),
sayfada beklenen parçalar var (oynatıcı, tema, yardım, Ayarlar çekmecesi), `dubla-gui` doğru pencere komutunu kurar
ve ancak pencere kapanıp sayfa sustuğunda kapanır. Tarayıcı açılmaz."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dublaj_hatti import masaustu

STATIK = Path(__file__).resolve().parents[1] / "src" / "dublaj_hatti" / "web_statik"
CSS = (STATIK / "app.css").read_text(encoding="utf-8")
HTML = (STATIK / "index.html").read_text(encoding="utf-8")


def _renkler(blok: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b", blok))


def _parlaklik(onaltilik: str) -> float:
    def kanal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(onaltilik[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((_parlaklik(a), _parlaklik(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _temalar() -> dict[str, dict[str, str]]:
    acik = _renkler(CSS[CSS.index(":root {"):CSS.index("}", CSS.index(":root {"))])
    bas = CSS.index(':root[data-tema="koyu"] {')
    koyu = _renkler(CSS[bas:CSS.index("}", bas)])
    return {"gündüz": acik, "gece": koyu}


@pytest.mark.parametrize("tema", ["gündüz", "gece"])
def test_renkler_okunur_ve_goz_yormaz(tema):
    r = _temalar()[tema]
    for yazi, zemin in (("yazi", "zemin"), ("yazi", "kart"), ("soluk", "kart"), ("soluk", "zemin"), ("ana", "kart"),
                        ("ana-yazi", "ana"), ("hata", "kart"), ("tamam", "kart"),
                        ("hata-yazi", "hata"), ("ov-yazi", "video"), ("ov-soluk", "video"), ("ov-isaret", "video"),
                        ("ov-vurgu", "video"), ("ov-vurgu-yazi", "ov-vurgu")):
        oran = kontrast(r[yazi], r[zemin])
        assert oran >= 4.5, f"{tema}: {yazi}/{zemin} = {oran:.2f} (en az 4.5)"
    assert kontrast(r["yazi"], r["zemin"]) < 17, "saf siyah/beyaz yok: aşırı kontrast göz yorar"
    assert r["zemin"].lower() not in ("#000000", "#ffffff")


def test_gece_rengi_iki_yerde_ayni():
    """Elle seçilen gece (data-tema=koyu) ile bilgisayarın gece ayarı aynı renkleri kullanır."""
    bas = CSS.index(':root:not([data-tema="acik"]) {')
    assert _renkler(CSS[bas:CSS.index("}", bas)]) == _temalar()["gece"]


def test_sayfada_beklenen_parcalar():
    for parca in ('id="video"', 'id="oynat"', 'id="konum"', 'id="ses"', 'id="hiz"', 'id="tam-ekran"',
                  'id="surum-orijinal"', 'id="surum-dublaj"', 'id="altyazi"', 'id="tema"', 'id="yardim"',
                  'class="cekmece"', 'id="ayar-ara"', 'id="dosya-alani"', 'name="color-scheme"'):
        assert parca in HTML, parca
    assert "prefers-color-scheme: dark" in CSS and "prefers-reduced-motion: reduce" in CSS
    js = (STATIK / "app.js").read_text(encoding="utf-8")
    assert "URL.createObjectURL(dosya)" in js  # seçilen video yüklenmeden oynar
    assert '"/api/nabiz"' in js and "beforeunload" in js


def test_pencere_komutu_ayri_profil_ve_uygulama_kipi(tmp_path):
    komut = masaustu.pencere_komutu("edge", "http://127.0.0.1:1/?t=x", tmp_path, konum="-3000,0")
    assert komut[0] == "edge" and "--app=http://127.0.0.1:1/?t=x" in komut
    assert f"--user-data-dir={tmp_path}" in komut and "--window-position=-3000,0" in komut


def test_pencere_kapaninca_ve_sayfa_susunca_kapanir():
    assert not masaustu.kapanmali(False, 0.0, 1000.0)  # pencere süreci sürüyor
    assert not masaustu.kapanmali(True, 990.0, 1000.0)  # süreç devretti ama sayfa yokluyor
    assert masaustu.kapanmali(True, 900.0, 1000.0)


def test_tarayici_yoksa_none(monkeypatch, tmp_path):
    for ad in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        monkeypatch.setenv(ad, str(tmp_path))
    monkeypatch.setattr(masaustu.shutil, "which", lambda ad: None)
    monkeypatch.setattr(masaustu.sys, "platform", "linux")
    assert masaustu.pencere_tarayicisi() is None


JS = (STATIK / "app.js").read_text(encoding="utf-8")


def test_tek_onay_penceresi_window_confirm_yok():
    """Riskli eylemler sayfa içi <dialog id="onay"> ile sorulur; tarayıcının confirm/alert/prompt penceresi yok."""
    assert not re.search(r"(window\.)?(confirm|alert|prompt)\(", JS)
    assert '<dialog id="onay"' in HTML and 'id="onay-vazgec"' in HTML and 'id="onay-tamam"' in HTML
    assert "function onayIste(" in JS and "showModal()" in JS
    # lisans, durdur, iş iptali ve arşivleme bu bileşeni kullanır
    assert JS.count("onayIste(") >= 5
    assert 'role="status"' in HTML and "function bildir(" in JS


def test_simge_sprite_tam_ve_emoji_yok():
    for kimlik in ("sil", "kopyala", "kalem", "durdur", "tamam", "mikrofon", "klasor", "arsiv"):
        assert f'<symbol id="s-{kimlik}" viewBox="0 0 24 24">' in HTML, kimlik
    kullanilan = set(re.findall(r'href="#(s-[a-z]+)"', HTML)) | set(re.findall(r'"(s-[a-z]+)"', JS))
    tanimli = set(re.findall(r'<symbol id="(s-[a-z]+)"', HTML))
    assert kullanilan <= tanimli, kullanilan - tanimli
    emoji = re.compile("[🌀-🫿☀-➿⏱✨]")
    assert not emoji.search(JS), "simge yerine emoji kullanılmaz"


def test_css_renk_yalniz_belirteclerde():
    """Sabit renk yok: onaltılık renk yalnız :root belirteç bloklarında."""
    disarida = re.sub(r"(:root[^{]*\{[^}]*\})", "", CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}", disarida)


def test_kayma_ve_hareket_kurallari():
    assert "scrollbar-gutter: stable" in CSS
    assert re.search(r"\.hata \{[^}]*min-height", CSS) and "visibility: hidden" in CSS
    assert "nabiz" not in CSS
    assert "animation: none !important" in CSS and "transition: none !important" in CSS
    assert not re.search(r"min-height: (3[0-9]|[12]?[0-9])px", CSS), "dokunma alanı en az 44 px"
