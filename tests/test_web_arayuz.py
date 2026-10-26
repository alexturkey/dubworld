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
                        ("uyari", "kart"), ("uyari", "zemin"), ("yazi", "ana-acik"), ("ana", "zemin"),
                        ("hata-yazi", "hata"), ("ov-yazi", "video"), ("ov-soluk", "video"), ("ov-isaret", "video"),
                        ("ov-vurgu", "video"), ("ov-vurgu-yazi", "ov-vurgu"),
                        ("soluk", "ana-acik"), ("hata", "zemin"), ("tamam", "zemin")):  # Sesler: çip sayısı, durum satırı
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
    assert not re.search(r"\b(window\.)?(confirm|alert|prompt)\(", JS)
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
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", disarida)


def test_kayma_ve_hareket_kurallari():
    assert "scrollbar-gutter: stable" in CSS
    assert re.search(r"\.hata \{[^}]*min-height", CSS) and "visibility: hidden" in CSS
    assert "nabiz" not in CSS
    assert "animation: none !important" in CSS and "transition: none !important" in CSS
    assert not re.search(r"min-height: (3[0-9]|[12]?[0-9])px", CSS), "dokunma alanı en az 44 px"


def test_oynatici_tam_ekran_cikis_ve_kontrol_cubugu():
    """Videonun içinde sağ üstte görünür tam ekran ve çıkış ikonu; çubuk altta, 3 sn sonra saklanır; kutu sabit, oran sığar."""
    assert 'id="tam-ekran"' in HTML and 'id="tam-cik"' in HTML
    assert '<symbol id="s-tam"' in HTML and '<symbol id="s-kucult"' in HTML
    assert re.search(r"\.kose-dugme \{[^}]*position: absolute; top: 8px; right: 8px", CSS)
    assert "object-fit: contain" in CSS and "aspect-ratio: 16 / 9" in CSS
    assert re.search(r"\.kontroller \{ position: absolute;[^}]*bottom: 0", CSS) and "var(--ov-gradyan1)" in CSS
    assert ".kontrol-gizli .kontroller" in CSS and "translateY(100%)" in CSS and "cursor: none" in CSS
    assert "setTimeout(kontrolGizleDene, 3000)" in JS and 'addEventListener("dblclick", tamEkranDegistir)' in JS
    for olay in ("pointermove", "pointerdown", "keydown", "focusin"):
        assert f'kutuOynatici.addEventListener("{olay}"' in JS, olay
    assert ".zaman-cizgisi { position: relative; height: 44px" in CSS
    # yaygın oynatıcı beklentileri: bekleme işareti, yeniden oynat, hatırlanan ses, sekmeli zaman
    for parca in ('id="bekleme"', 'id="yeniden-oynat"', 'id="video-mesaj"'):
        assert parca in HTML, parca
    assert "dubworld.ses" in JS and "localStorage.setItem(YEREL_SES" in JS
    assert "font-variant-numeric: tabular-nums" in CSS
    for tus in ('"arrowleft"', '"arrowright"', '"m"', '"f"', '" "', '"k"'):
        assert tus in JS, tus


def test_video_alani_isin_videosunu_gosterir():
    """İş sürerken ve bitince alan o işin kaynağını/sonucunu gösterir; sayfa yenilense de; sunulamıyorsa kısa mesaj."""
    for parca in ("function isBagla(", "function acilistaIsiBagla(", "function isTakip(", '"/api/isler"', "oynatici.kaynak_yok",
                  "oynatici.baglanti_bekle", "bekleyenYerel"):
        assert parca in JS, parca


def test_inceleme_paneli_parcalari():
    for parca in ('id="inceleme"', 'id="inceleme-devam"', 'id="inceleme-kapat"', 'id="bul-ara"', 'id="bul-yeni"',
                  'id="bul-degistir"', 'id="inceleme-liste"', 'id="inceleme-durum"', 'id="gozden-kutusu"',
                  'id="inceleme-seridi"', 'id="indir"', 'id="baska-dil"', 'role="tablist"', 'class="rozet"'):
        assert parca in HTML, parca
    for parca in ('"/api/duzenle"', '"/api/cevir_satir"', '"/api/devam"', "tts_ve_segment_sesleri", "OTO_KAYIT_MS = 1500",
                  "SAAT_SINIRI = 15", "tek_satir_desteklenmiyor", "is_inceleme_degil", "a_genel.gozden_gecir", "geriAl:",
                  "onayIste({ baslik: t(\"onay.devam_baslik\")"):
        assert parca in JS, parca
    # dar ekran: 700 altı alt sayfa, 450 altı tam ekran; panel hareketi yalnız transform + opacity
    assert "max-width: 699px" in CSS and "max-width: 449px" in CSS
    assert re.search(r"@keyframes panel-gel \{ from \{ transform: translateX\(16px\); opacity: 0; \}", CSS)
    assert ".iskelet" in CSS and "grid-template-columns" in CSS
    assert not re.search(r"(window\.)?confirm\(", JS)



def test_sesler_sekmesi_parcalari():
    """Sesler sekmesi: ses kitaplığı listesi, ses ekle sayfası (görünür kapatma, sayaç, neden satırı), Dublaj kartında ses seçici."""
    for parca in ('data-sekme="sesler"', 'id="sesler"', 'id="ses-ekle-ac"', 'id="ses-ara"', 'id="ses-cipler"', 'id="ses-liste"',
                  'id="ses-bos"', '<dialog id="ses-form"', 'id="ses-form-kapat"', 'id="ses-dosya"', 'id="ses-onizleme-ses"',
                  'id="ses-ad"', 'id="ses-kategori-secimi"', 'id="ses-metin"', 'name="ses-riza"', 'id="ses-taklit"', 'id="ses-kaydet"',
                  'id="ses-neden"', 'id="ses-secici"', 'id="ses-yonet"', 's-mikrofon', 'id="s-ara"', 'maxlength="60"', 'maxlength="600"'):
        assert parca in HTML, parca
    for parca in ('"/api/sesler"', '"/api/ses_ekle"', '"/api/ses_guncelle"', '"/api/ses_sil"', '"/api/xtts_lisans"', "X-Ses-Metin",
                  "X-Ses-Riza", "X-Ses-Taklit-Yok", "function sesSec(", "function listeEsitle(", "kitaplik/", "ses.voxcpm2_ses", "ses.motor",
                  "sesOnceki", "dubworld.ses_secimi", "onayIste({ baslik: t(\"sesler.sil_baslik\"", "xtts.kurulu", "voxcpm2.kurulu",
                  "Number.isFinite(a.duration)", "upload.onprogress"):
        assert parca in JS, parca
    assert not re.search(r"(window\.)?(confirm|alert|prompt)\(", JS)
    assert "min-height" in re.search(r"\.neden \{[^}]*\}", CSS).group(0) and "button.ilerliyor::before" in CSS
    # etiketsiz simge yok: JS ile kurulan simge düğmeleri etiketle(...) ile ad alır
    assert JS.count("etiketle(") >= 6


def test_panel_ust_bolumu_yapiskan_ve_satir_ust_kismi_kaymaz():
    """Not + bul-değiştir satırı kayan listenin dışında (yapışkan); satır üst bölümü grid: durum yazısı uzasa da satır büyümez."""
    assert 'class="inceleme-yapisik"' in HTML and 'id="inceleme-is"' in HTML
    assert re.search(r"\.inceleme-govde \{[^}]*overflow: hidden", CSS)
    assert re.search(r"\.inceleme-liste \{[^}]*overflow: auto", CSS)
    assert re.search(r"\.irow-ust \{[^}]*display: grid", CSS)
    assert "function otoBuyutToplu(" in JS and JS.count("otoBuyutToplu(") >= 4


def test_ses_suzgeci_kaymaz_ve_pasif_baslat_nedenini_soyler():
    """Süzgeç/arama: liste yüksekliği tutulur, kalan kartlar transform ile süzülür. Pasif Başlat: neden satırı yeri ayrılı,
    her pasif neden tek kapıdan (baslatGuncelle) geçer ve tr+en sözlükte karşılığı vardır; Ses seçici kapalı açılır liste kalır."""
    import json

    assert "function listeKaymasiz(" in JS and "listeKaymasiz(kap, () => listeEsitle(kap, istenen))" in JS
    assert 'kap.style.minHeight = yukseklik + "px"' in JS and "hareketAz() ? \"none\"" in JS
    assert 'id="baslat-neden"' in HTML and re.search(r"\.baslat-neden \{[^}]*min-height", CSS)
    assert JS.count('$("dublajla").disabled') == 1  # başka yerden pasif/aktif yapılmaz: yalnız baslatGuncelle
    nedenler = set(re.findall(r'return "(calisiyor|yukleniyor|video|voxcpm2)"', JS))
    assert nedenler == {"calisiyor", "yukleniyor", "video", "voxcpm2"}
    sozlukler = [json.loads((STATIK.parent / "arayuz_dilleri" / f"{d}.json").read_text(encoding="utf-8")) for d in ("tr", "en")]
    for sozluk in sozlukler:
        for neden in nedenler:
            assert sozluk.get("baslat.neden." + neden, "").strip(), neden
    assert 'id="ses-secici"' in HTML and re.search(r'<select id="ses-secici"(?![^>]*(size|multiple))', HTML)


def test_konsolsuz_acilista_akislar_gunluge_baglanir(tmp_path, monkeypatch):
    # pythonw: sys.stdout/stderr None; bağlanmazsa her istek boş yanıtla kapanır (ERR_EMPTY_RESPONSE)
    monkeypatch.setattr(masaustu.sys, "stdout", None)
    monkeypatch.setattr(masaustu.sys, "stderr", None)
    masaustu.akislari_bagla(tmp_path / "cikti")
    gunluk = masaustu.sys.stderr
    gunluk.write("web: deneme\n")
    monkeypatch.undo()
    gunluk.close()
    assert "web: deneme" in (tmp_path / "cikti" / "dubla-gui.log").read_text(encoding="utf-8")
