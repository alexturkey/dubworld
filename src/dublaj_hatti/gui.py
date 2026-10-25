"""`dubla-gui`: masaüstü arayüzü (tkinter; Python ile gelir, ek paket yok).

İki sekme:
  * Önerilen akış: video seç → dil seç → "<Dil> dublajla" (önerilen varsayılanlar) ya da "Yalnız altyazı / metin çıkar"
    (dil seçicisi Gelişmiş'teki genel.hedef_dil'in kendisidir: tek ayar, iki görünüm)
  * Gelişmiş: bütün ayarlar, varsayılan dosyadaki açıklamalarıyla; değiştirilenler işaretlenir
Yazılar arayüz dilinde (`arayuz_dili`, sağ üstteki dil kutusu; iş yokken pencere yeni dille yeniden kurulur).

İş, `dubla` komut satırının ayrı (penceresiz) bir sürecinde çalışır; arayüz donmaz, kapatınca iş durur.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from dublaj_hatti import __version__, arayuz_dili, kayit
from dublaj_hatti.arayuz_dili import t
from dublaj_hatti.gui_ilerleme import ADIM_MS, IlerlemePanosu
from dublaj_hatti.is_yurutucu import IsYurutucu, ayar_formu, cikti_klasoru_ac
from dublaj_hatti.yapilandirma import AyarHatasi, ayarlari_yukle

VIDEO_UZANTILARI = "*.mp4 *.mkv *.mov *.webm *.avi *.m4v"


def onerilen_aciklama() -> str:
    return "\n\n".join(t(f"onerilen.not{i}") for i in range(1, 5))


def durum_yazisi(durum: str) -> str:
    return t(f"ilerleme.{durum}") if durum != "bos" else ""


def kurulum_eksikleri() -> list[str]:
    """İlk açılış denetimi (torch yüklemez): Önerilen akışın eksik parçaları; `dubla kontrol` ile aynı ölçüt."""
    from dublaj_hatti import kayit
    from dublaj_hatti.bolum_00_omurga.runtime.arac_yolu import arac_bul
    from dublaj_hatti.cli import onerilen_akis_eksikleri

    ffmpeg = arac_bul("ffmpeg")  # kurulu kopya ya da PATH'in mutlak klasörleri; çalışma klasörüne bakılmaz
    rapor: dict[str, Any] = {"ffmpeg": "var" if ffmpeg else ""}
    rapor.update({grup: kayit.durum(grup) for grup in ("stt", "ceviri", "tts", "ek")})
    return onerilen_akis_eksikleri(rapor)


class AyarAlani:
    """Gelişmiş sekmesindeki tek ayar satırı."""

    def __init__(self, ust: ttk.Frame, satir: int, alan: dict[str, Any]) -> None:
        self.alan = alan
        self.etiket = ttk.Label(ust, text=alan["anahtar"], font=("Consolas", 9))  # anahtar çevrilmez: dosyadaki adı
        self.etiket.grid(row=satir, column=0, sticky="nw", padx=(4, 12), pady=(6, 0))
        if alan["tur"] == "evet_hayir":
            self.degisken: tk.Variable = tk.BooleanVar(value=bool(alan["deger"]))
            girdi: tk.Widget = ttk.Checkbutton(ust, variable=self.degisken)
        elif alan["tur"] == "secim":
            # donanım etiketi seçeneğin yanında yazar ("CPU'da yavaş" ...); motor gizlenmez (docs/donanim.md)
            self.etiketler: dict[str, str] = dict(alan.get("etiketler") or {})
            self.degisken = tk.StringVar(value=self._gorunen(str(alan["deger"])))
            girdi = ttk.Combobox(ust, textvariable=self.degisken, state="readonly", width=46,
                                 values=[self._gorunen(str(s)) for s in alan["secenekler"]])
            self.kutu = girdi
            self.secenekler: list[str] = [str(s) for s in alan["secenekler"]]
        else:
            self.degisken = tk.StringVar(value="" if alan["deger"] is None else str(alan["deger"]))
            girdi = ttk.Entry(ust, textvariable=self.degisken, width=36)
        girdi.grid(row=satir, column=1, sticky="w", pady=(6, 0))
        aciklama = alan["aciklama"]
        if alan.get("ses_secenekleri"):  # konuşmacı başına ses: seçilebilecek sesler (docs/sesler.md)
            aciklama += f" · {t('ayar.sesler')}: " + "; ".join(f"{tts}: {', '.join(v)}" for tts, v in alan["ses_secenekleri"].items() if v)
        if aciklama:
            ttk.Label(ust, text=aciklama, wraplength=560, foreground="#5d6677").grid(
                row=satir + 1, column=1, sticky="w")
        self.degisken.trace_add("write", lambda *_: self._isaretle())

    def _gorunen(self, secenek: str) -> str:
        etiket = getattr(self, "etiketler", {}).get(secenek, "")
        return f"{secenek}  ·  {etiket}" if etiket else secenek

    def secenekleri_degistir(self, secenekler: list[str], etiketler: dict[str, str]) -> None:
        """Bağlı süzgeç (ör. hedef dil ← ses.motor): liste değişir; geçerli değer listede yoksa ilk seçenek."""
        self.etiketler = etiketler
        self.secenekler = list(secenekler)
        gecerli = self.deger()
        self.kutu.configure(values=[self._gorunen(s) for s in secenekler])
        self.degisken.set(self._gorunen(gecerli if gecerli in secenekler else secenekler[0]))

    def deger(self) -> Any:
        ham = self.degisken.get()
        tur = self.alan["tur"]
        if tur == "secim":
            return str(ham).split("  ·  ", 1)[0]
        if tur == "tam_sayi":
            return int(str(ham).strip())
        if tur == "ondalik":
            return float(str(ham).strip().replace(",", "."))
        return ham

    def degisti_mi(self) -> bool:
        try:
            return self.deger() != self.alan["deger"]
        except ValueError:
            return True

    def _isaretle(self) -> None:
        self.etiket.configure(foreground="#2457c5" if self.degisti_mi() else "")

    def sifirla(self) -> None:
        self.yaz(self.alan["deger"])

    def yaz(self, deger: Any) -> None:
        if self.alan["tur"] == "secim":
            self.degisken.set(self._gorunen(str(deger)))
            return
        self.degisken.set(bool(deger) if self.alan["tur"] == "evet_hayir" else ("" if deger is None else str(deger)))


class Uygulama:
    def __init__(self, kok: tk.Tk, yurutucu: IsYurutucu | None = None) -> None:
        self.kok = kok
        self.yurutucu = yurutucu or IsYurutucu(arayuz="gui")
        self.video: Path | None = None
        self.baglanti: str | None = None  # https bağlantısı (isteğe bağlı yt-dlp / gallery-dl)
        self.alanlar: list[AyarAlani] = []
        self._zamanlayicilar: list[str] = []  # dil değişince pencere yeniden kurulur; eski döngüler durdurulur
        self._yuvalar: dict[int, str] = {}
        kok.title(f"DubWorld {__version__}")
        kok.minsize(820, 600)
        kok.protocol("WM_DELETE_WINDOW", self.kapat)

        self._dil_satiri(kok)
        sekmeler = ttk.Notebook(kok)
        sekmeler.pack(fill="both", expand=True, padx=10, pady=(4, 4))
        sekmeler.add(self._onerilen_sekmesi(sekmeler), text=f"  {t('sekme.onerilen')}  ")
        sekmeler.add(self._gelismis_sekmesi(sekmeler), text=f"  {t('sekme.gelismis')}  ")
        from dublaj_hatti.gui_isler import IslerSekmesi  # iş geçmişi, sorunlu işler, devam (is_yonetimi)

        self.isler = IslerSekmesi(sekmeler, self.yurutucu, self.degisiklikler)
        sekmeler.add(self.isler.cerceve, text=f"  {t('sekme.isler')}  ")
        sekmeler.bind("<<NotebookTabChanged>>",
                      lambda _e: self.isler.yenile() if sekmeler.select() == str(self.isler.cerceve) else None)
        self._ilerleme_alani(kok)
        self._sonra(1000, self._yokla)

    def _sonra(self, ms: int, islev: Any, yer: int | None = None) -> None:
        """Zamanlayıcı; `yer` verilirse o sabit yuvada tutulur (sık dönen animasyon ötekileri listeden itmesin)."""
        kimlik = self.kok.after(ms, islev)
        if yer is not None:
            self._yuvalar[yer] = kimlik
        else:
            self._zamanlayicilar = [*self._zamanlayicilar[-8:], kimlik]  # son birkaçı yeter

    # --- arayüz dili ---------------------------------------------------------------------------------
    def _dil_satiri(self, kok: tk.Tk) -> None:
        """Sağ üstte arayüz dili kutusu: diller kendi adıyla ("Türkçe", "English")."""
        satir = ttk.Frame(kok)
        satir.pack(fill="x", padx=10, pady=(8, 0))
        self._arayuz_eslesme = {arayuz_dili.kendi_adi(k): k for k in arayuz_dili.mevcut_diller()}
        self.arayuz_degisken = tk.StringVar(value=arayuz_dili.kendi_adi(arayuz_dili.secili()))
        kutu = ttk.Combobox(satir, textvariable=self.arayuz_degisken, state="readonly", width=14,
                            values=list(self._arayuz_eslesme))
        kutu.pack(side="right")
        kutu.bind("<<ComboboxSelected>>", self._arayuz_dili_secildi)
        ttk.Label(satir, text=t("arayuz.dil")).pack(side="right", padx=(0, 6))

    def _arayuz_dili_secildi(self, _olay: Any = None) -> None:
        kod = self._arayuz_eslesme.get(self.arayuz_degisken.get())
        if not kod or kod == arayuz_dili.secili():
            return
        if self.yurutucu.calisiyor():
            messagebox.showinfo(t("arayuz.dil"), t("arayuz.dil_is_suruyor"), parent=self.kok)
            self.arayuz_degisken.set(arayuz_dili.kendi_adi(arayuz_dili.secili()))
            return
        self.dili_degistir(kod)

    def dili_degistir(self, kod: str) -> Uygulama:
        """Pencereyi yeni dille yeniden kurar; seçilen video, bağlantı ve Gelişmiş'teki değişiklikler korunur."""
        try:
            degisen = self.degisiklikler()
        except AyarHatasi:  # yarım yazılmış sayı: o alan taşınmaz
            degisen = {a.alan["anahtar"]: a.deger() for a in self.alanlar if a.alan["tur"] not in ("tam_sayi", "ondalik")
                       and a.degisti_mi()}
        video, baglanti = self.video, self.baglanti
        for zaman in [*self._zamanlayicilar, *self._yuvalar.values()]:
            try:
                self.kok.after_cancel(zaman)
            except tk.TclError:
                pass
        for parca in self.kok.winfo_children():
            parca.destroy()
        arayuz_dili.ayarla(kod)
        yeni = Uygulama(self.kok, self.yurutucu)
        for alan in yeni.alanlar:
            if alan.alan["anahtar"] in degisen:
                alan.yaz(degisen[alan.alan["anahtar"]])
        yeni.video, yeni.baglanti = video, baglanti
        if video is not None or baglanti:
            yeni.video_yazi.configure(text=video.name if video is not None else str(baglanti)[:70])
        yeni._dugmeleri_ayarla()
        return yeni

    # --- sekmeler --------------------------------------------------------------------------------------
    def _onerilen_sekmesi(self, ust: ttk.Notebook) -> ttk.Frame:
        cerceve = ttk.Frame(ust, padding=16)
        # Kurulum eksikse ilk açılışta açık uyarı (pencere çizildikten sonra denetlenir; boşsa görünmez).
        self.kurulum_uyari = ttk.Label(cerceve, text="", foreground="#b3261e", wraplength=720, justify="left")
        self.kurulum_uyari.pack(anchor="w")
        self._sonra(300, self._kurulumu_denetle)
        ttk.Label(cerceve, text=t("adim.video"), font=("Segoe UI", 11, "bold")).pack(anchor="w")
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        ttk.Button(satir, text=t("dugme.video_sec"), command=self.video_sec).pack(side="left")
        self.video_yazi = ttk.Label(satir, text=t("video.secilmedi"))
        self.video_yazi.pack(side="left", padx=10)
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=(0, 6))
        ttk.Label(satir, text=t("baglanti.etiket")).pack(side="left")
        self.baglanti_degisken = tk.StringVar()
        ttk.Entry(satir, textvariable=self.baglanti_degisken, width=52).pack(side="left", padx=6)
        ttk.Button(satir, text=t("dugme.baglanti"), command=self.baglanti_kullan).pack(side="left")
        # Dublaj dili: Gelişmiş'teki genel.hedef_dil alanına bağlanır (_onerilen_dili_bagla); ayrı bir ayar tutulmaz.
        ttk.Label(cerceve, text=t("adim.dil"), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 0))
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        self.dil_degisken = tk.StringVar()
        self.dil_kutu = ttk.Combobox(satir, textvariable=self.dil_degisken, state="readonly", width=28)
        self.dil_kutu.pack(side="left")
        self.dil_kutu.bind("<<ComboboxSelected>>", self._onerilen_dil_secildi)
        self._dil_eslesme: dict[str, str] = {}
        ttk.Label(cerceve, text=t("adim.baslat"), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 0))
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        self.dublajla_dugme = ttk.Button(satir, text=kayit.dublajla_etiketi("tr"), command=lambda: self.baslat("dublaj"),
                                         state="disabled")
        self.dublajla_dugme.pack(side="left")
        self.transkript_dugme = ttk.Button(satir, text=t("dugme.transkript"),
                                           command=lambda: self.baslat("transkript"), state="disabled")
        self.transkript_dugme.pack(side="left", padx=8)
        ttk.Label(cerceve, text=onerilen_aciklama(), wraplength=720, foreground="#5d6677",
                  justify="left").pack(anchor="w", pady=(14, 0))
        return cerceve

    def _gelismis_sekmesi(self, ust: ttk.Notebook) -> ttk.Frame:
        dis = ttk.Frame(ust, padding=(8, 8))
        ust_satir = ttk.Frame(dis)
        ust_satir.pack(fill="x")
        ttk.Label(ust_satir, text=t("gelismis.not"), foreground="#5d6677", wraplength=640,
                  justify="left").pack(side="left")
        ttk.Button(ust_satir, text=t("dugme.varsayilan"), command=self.sifirla).pack(side="right")
        tuval = tk.Canvas(dis, highlightthickness=0)
        kaydirma = ttk.Scrollbar(dis, orient="vertical", command=tuval.yview)
        ic = ttk.Frame(tuval)
        ic.bind("<Configure>", lambda _e: tuval.configure(scrollregion=tuval.bbox("all")))
        tuval.create_window((0, 0), window=ic, anchor="nw")
        tuval.configure(yscrollcommand=kaydirma.set)
        tuval.pack(side="left", fill="both", expand=True, pady=(8, 0))
        kaydirma.pack(side="right", fill="y", pady=(8, 0))
        tuval.bind_all("<MouseWheel>", lambda e: tuval.yview_scroll(int(-e.delta / 120), "units"))
        satir, bolum = 0, ""
        for alan in ayar_formu():
            if alan["bolum"] != bolum:
                bolum = alan["bolum"]
                ttk.Label(ic, text=t(f"bolum.{bolum}") if arayuz_dili.var_mi(f"bolum.{bolum}", "tr")
                          else bolum.replace("_", " ").capitalize(), font=("Segoe UI", 10, "bold")).grid(
                    row=satir, column=0, columnspan=2, sticky="w", pady=(14, 2))
                satir += 1
            self.alanlar.append(AyarAlani(ic, satir, alan))
            satir += 2
        self._suzgecleri_bagla()
        self._onerilen_dili_bagla()
        return dis

    def _suzgecleri_bagla(self) -> None:
        """Hedef dil listesi seçili TTS'e göre süzülür (docs/diller.md); denenmemiş dil etiketle görünür."""
        alanlar = {a.alan["anahtar"]: a for a in self.alanlar}
        for alan in self.alanlar:
            suzgec = alan.alan.get("suzgec")
            kaynak = alanlar.get(suzgec["anahtar"]) if suzgec else None
            if not suzgec or kaynak is None or not hasattr(alan, "kutu"):
                continue

            def uygula(*_: Any, hedef: AyarAlani = alan, bagli: AyarAlani = kaynak, tablo: dict = suzgec["degerler"]) -> None:
                v = tablo.get(bagli.deger())
                if v:
                    hedef.secenekleri_degistir(v["izinli"], dict.fromkeys(v["denenmemis"], t("ayar.denenmedi_uyari")))

            kaynak.degisken.trace_add("write", uygula)
            uygula()

    # --- Önerilen sekmesindeki dil seçicisi = Gelişmiş'teki genel.hedef_dil (tek kaynak) -----------------------
    def _dil_alani(self) -> AyarAlani | None:
        return next((a for a in self.alanlar if a.alan["anahtar"] == "genel.hedef_dil" and hasattr(a, "kutu")), None)

    def _onerilen_dili_bagla(self) -> None:
        alan = self._dil_alani()
        if alan is None:
            self.dil_kutu.configure(state="disabled")
            return
        alan.degisken.trace_add("write", lambda *_: self._onerilen_dili_esitle())
        self._onerilen_dili_esitle()

    def _onerilen_dili_esitle(self) -> None:
        """Gelişmiş alanındaki değeri ve (ses motoruna göre süzülmüş) seçenekleri Önerilen'e yansıtır, düğmeyi adlandırır.

        Dil adı arayüz dilinde, farklıysa yanında dilin kendi adı: "Almanca (Deutsch)", "German (Deutsch)".
        """
        alan = self._dil_alani()
        if alan is None:
            return

        def gorunen(kod: str) -> str:
            ad = arayuz_dili.dil_secenegi(kod)
            return f"{ad}  ·  {t('dil.denenmedi')}" if alan.etiketler.get(kod) else ad

        self._dil_eslesme = {gorunen(k): k for k in alan.secenekler}
        self.dil_kutu.configure(values=list(self._dil_eslesme))
        kod = alan.deger()
        self.dil_degisken.set(gorunen(kod))
        self.dublajla_dugme.configure(text=kayit.dublajla_etiketi(kod))

    def _onerilen_dil_secildi(self, _olay: Any = None) -> None:
        alan = self._dil_alani()
        kod = self._dil_eslesme.get(self.dil_degisken.get())
        if alan is not None and kod and kod != alan.deger():
            alan.degisken.set(alan._gorunen(kod))  # Gelişmiş alanı değişir; iz (trace) Önerilen'i eşitler

    def _ilerleme_alani(self, kok: tk.Tk) -> None:
        cerceve = ttk.Frame(kok, padding=(10, 4, 10, 10))
        sekmeler = next(c for c in kok.pack_slaves() if isinstance(c, ttk.Notebook))
        cerceve.pack(fill="x", side="bottom", before=sekmeler)  # pencere küçülünce sekme daralır, pano hep görünür
        self.pano = IlerlemePanosu(cerceve)
        self._sonra(ADIM_MS, self._canlandir, yer=0)
        dugmeler = ttk.Frame(cerceve)
        dugmeler.pack(fill="x")
        self.durdur_dugme = ttk.Button(dugmeler, text=t("dugme.durdur"), command=self.yurutucu.durdur, state="disabled")
        self.durdur_dugme.pack(side="left")
        self.oynat_dugme = ttk.Button(dugmeler, text=t("dugme.videoyu_ac"), command=self.videoyu_ac, state="disabled")
        self.oynat_dugme.pack(side="left", padx=6)
        self.klasor_dugme = ttk.Button(dugmeler, text=t("dugme.cikti_klasoru"), command=self.klasoru_ac,
                                       state="disabled")
        self.klasor_dugme.pack(side="left")
        self.gunluk_dugme = ttk.Button(dugmeler, text=t("dugme.gunluk_goster"), command=self.gunluk_ac_kapa)
        self.gunluk_dugme.pack(side="right")
        self.gunluk = ScrolledText(cerceve, height=10, font=("Consolas", 9), state="disabled")
        self.gunluk_acik = False

    # --- eylemler --------------------------------------------------------------------------------------
    def _kurulumu_denetle(self) -> None:
        try:
            eksik = kurulum_eksikleri()
        except Exception as hata:  # denetim arayüzü hiçbir zaman düşürmez
            eksik = [t("kurulum.denetlenemedi", None, hata=hata)]
        if eksik:
            self.kurulum_uyari.configure(text=t("kurulum.eksik", None, eksik=", ".join(eksik)) + "\n")

    def video_sec(self) -> None:
        yol = filedialog.askopenfilename(title=t("pencere.video_sec"),
                                         filetypes=[(t("dosya.video"), VIDEO_UZANTILARI), (t("dosya.tumu"), "*.*")])
        if yol:
            self.video, self.baglanti = Path(yol), None
            self.video_yazi.configure(text=self.video.name)
            self._dugmeleri_ayarla()

    def degisiklikler(self) -> dict[str, Any]:
        cikti = {}
        for alan in self.alanlar:
            if alan.degisti_mi():
                try:
                    cikti[alan.alan["anahtar"]] = alan.deger()
                except ValueError as hata:
                    raise AyarHatasi(t("ayar.sayi_bekleniyor", None, anahtar=alan.alan["anahtar"])) from hata
        return cikti

    def baglanti_kullan(self) -> None:
        """Bağlantıyı doğrular: türüne göre yalnız gereken isteğe bağlı araç aranır, yoksa kurulum ipucu gösterilir."""
        from dublaj_hatti.kaynak_girdisi import KaynakHatasi, kaynak_dogrula

        try:
            self.baglanti = kaynak_dogrula(self.baglanti_degisken.get())
        except KaynakHatasi as hata:
            messagebox.showerror(t("hata.baglanti"), str(hata), parent=self.kok)
            return
        self.video = None
        self.video_yazi.configure(text=self.baglanti[:70])
        self._dugmeleri_ayarla()

    def baslat(self, is_turu: str) -> None:
        kaynak = self.baglanti or (str(self.video) if self.video is not None else "")
        if not kaynak:
            return
        try:
            ayarlar = self.degisiklikler()
            ayarlar["genel.is_turu"] = is_turu
            komut = "transkript" if is_turu == "transkript" else "dubla"
            if not self._lisans_onayi(ayarlar):
                return
            self.yurutucu.baslat(kaynak, ayarlar, komut=komut)
        except (AyarHatasi, ValueError, RuntimeError) as hata:
            messagebox.showerror(t("hata.baslatilamadi"), str(hata), parent=self.kok)
            return
        self._dugmeleri_ayarla()

    def _lisans_onayi(self, ayarlar: dict[str, Any]) -> bool:
        """Ticari olmayan / şartlı motor ilk kez seçildiyse iki dilli uyarı + onay kutusu; onay hatırlanır."""
        from dublaj_hatti.lisans_onayi import LisansOnayiGerekli, arayuz_kapisi

        try:
            arayuz_kapisi(ayarlar)
            return True
        except LisansOnayiGerekli as gerek:
            metin = "\n\n".join(m for _, m in gerek.bekleyen)
            if not messagebox.askyesno("Lisans onayı / License", metin + "\n\nKabul ediyor musunuz? / Do you accept?",
                                       icon="warning", default="no", parent=self.kok):
                return False
            arayuz_kapisi(ayarlar, onay=True)
            return True

    def sifirla(self) -> None:
        for alan in self.alanlar:
            alan.sifirla()

    def _sonuc_video(self) -> str:
        sonuc = self.yurutucu.durum.sonuc
        return str(sonuc.get("dubbed_video") or sonuc.get("output_video") or "")

    def videoyu_ac(self) -> None:
        yol = self._sonuc_video()
        if yol and Path(yol).is_file():
            if sys.platform == "win32":
                os.startfile(yol)  # noqa: S606 - kullanıcının tıklamasıyla, varsayılan oynatıcı
            else:
                cikti_klasoru_ac(yol)

    def klasoru_ac(self) -> None:
        sonuc = self.yurutucu.durum.sonuc
        hedef = sonuc.get("run_dir") or self._sonuc_video() or sonuc.get("transcript_path") or ""
        if hedef:
            cikti_klasoru_ac(str(hedef))

    def gunluk_ac_kapa(self) -> None:
        self.gunluk_acik = not self.gunluk_acik
        if self.gunluk_acik:
            self.gunluk.pack(fill="both", expand=True, pady=(6, 0))
        else:
            self.gunluk.pack_forget()
        self.gunluk_dugme.configure(text=t("dugme.gunluk_gizle") if self.gunluk_acik else t("dugme.gunluk_goster"))

    def _dugmeleri_ayarla(self) -> None:
        calisiyor = self.yurutucu.calisiyor()
        hazir = "normal" if (self.video is not None or self.baglanti) and not calisiyor else "disabled"
        self.dublajla_dugme.configure(state=hazir)
        self.transkript_dugme.configure(state=hazir)
        self.durdur_dugme.configure(state="normal" if calisiyor else "disabled")
        bitti = self.yurutucu.durum.durum == "bitti"
        self.oynat_dugme.configure(state="normal" if bitti and self._sonuc_video() else "disabled")
        self.klasor_dugme.configure(state="normal" if bitti else "disabled")

    def _yokla(self) -> None:
        d = self.yurutucu.durum.ozet()
        self.pano.guncelle(d, durum_yazisi(d["durum"]))
        if d["durum"] != "bos":
            self.gunluk.configure(state="normal")
            self.gunluk.delete("1.0", "end")
            self.gunluk.insert("end", "\n".join(d["gunluk"]))
            self.gunluk.see("end")
            self.gunluk.configure(state="disabled")
            if d["durum"] == "hata" and not getattr(self, "_hata_gosterildi", False):
                self._hata_gosterildi = True
                messagebox.showerror(t("hata.is_basarisiz"), d["hata"] or t("hata.ayrinti_gunlukte"), parent=self.kok)
            if d["durum"] == "calisiyor":
                self._hata_gosterildi = False
        self._dugmeleri_ayarla()
        self._sonra(1000, self._yokla)

    def _canlandir(self) -> None:
        self.pano.adim()
        self._sonra(ADIM_MS, self._canlandir, yer=0)

    def kapat(self) -> None:
        if self.yurutucu.calisiyor() and not messagebox.askyesno(
                t("cikis.baslik"), t("cikis.soru"), parent=self.kok):
            return
        self.yurutucu.kapat()
        self.kok.destroy()


def baslangic_dili() -> str:
    """Açılış dili: `genel.arayuz_dili` (auto = bilgisayarın dili); ayar dosyası okunamazsa da auto."""
    try:
        deger = ayarlari_yukle().get("genel.arayuz_dili")
    except (AyarHatasi, OSError, ValueError):
        deger = "auto"
    return arayuz_dili.ayarla(str(deger or "auto"))


def main(argv: list[str] | None = None) -> int:
    baslangic_dili()
    kok = tk.Tk()
    Uygulama(kok)
    kok.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
