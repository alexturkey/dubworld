"""`dubla-gui`: masaüstü arayüzü (tkinter; Python ile gelir, ek paket yok).

İki sekme:
  * Önerilen akış: video seç → dil seç → "<Dil> dublajla" (önerilen varsayılanlar) ya da "Yalnız altyazı / metin çıkar"
    (dil seçicisi Gelişmiş'teki genel.hedef_dil'in kendisidir: tek ayar, iki görünüm)
  * Gelişmiş: bütün ayarlar, varsayılan dosyadaki açıklamalarıyla; değiştirilenler işaretlenir

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

from dublaj_hatti import __version__, kayit
from dublaj_hatti.is_yurutucu import IsYurutucu, ayar_formu, cikti_klasoru_ac
from dublaj_hatti.yapilandirma import AyarHatasi

VIDEO_TURLERI = [("Video", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v"), ("Tümü", "*.*")]
ONERILEN_ACIKLAMA = (
    "Önerilen akış önerilen varsayılanlarla çalışır: konuşmayı yazıya döker, kelime zamanlarını hizalar, konuşmacıları "
    "ayırıp her birine kadın/erkek sesine uygun bir Türkçe ses verir, çevirir, seslendirir ve altyazıyı ekler.\n\n"
    "Ayarların hepsi \"Gelişmiş\" sekmesindedir; orada değiştirdiğiniz her şey buradaki düğmeler için de geçerlidir. "
    "Birlikte çalışmayan seçimler başlatırken açık hata mesajıyla durdurulur (docs/tarifler/kombinasyonlar.md).\n\n"
    "Başka bir dile dublaj: yukarıdaki \"Dublaj dili\" listesinden seçin (Gelişmiş sekmesindeki genel.hedef_dil ile "
    "aynı ayardır). Türkçe dışındaki diller ve İngilizce "
    "dışındaki kaynak videolar için bir LLM çeviri arka ucu gerekir (Codex, Claude Code ya da kendi API anahtarınız; "
    "docs/baslarken.md).\n\n"
    "Yalnız hakkınız olan ya da izinli içerik kullanın. Çıktıya \"yapay zekâ ile dublajlandı\" meta etiketi eklenir."
)
DURUM_YAZISI = {"calisiyor": "İş sürüyor", "bitti": "Bitti", "hata": "Hata", "durduruldu": "Durduruldu", "bos": ""}


def kurulum_eksikleri() -> list[str]:
    """İlk açılış denetimi (torch yüklemez): Önerilen akışın eksik parçaları; `dubla kontrol` ile aynı ölçüt."""
    import shutil

    from dublaj_hatti import kayit
    from dublaj_hatti.cli import onerilen_akis_eksikleri
    from dublaj_hatti.yapilandirma import PROJE_KOKU

    ffmpeg = (PROJE_KOKU / "runtime_assets" / "ffmpeg" / "bin").is_dir() or shutil.which("ffmpeg")
    rapor: dict[str, Any] = {"ffmpeg": "var" if ffmpeg else ""}
    rapor.update({grup: kayit.durum(grup) for grup in ("stt", "ceviri", "tts", "ek")})
    return onerilen_akis_eksikleri(rapor)


class AyarAlani:
    """Gelişmiş sekmesindeki tek ayar satırı."""

    def __init__(self, ust: ttk.Frame, satir: int, alan: dict[str, Any]) -> None:
        self.alan = alan
        self.etiket = ttk.Label(ust, text=alan["anahtar"], font=("Consolas", 9))
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
            aciklama += " · Sesler: " + "; ".join(f"{tts}: {', '.join(v)}" for tts, v in alan["ses_secenekleri"].items() if v)
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
        deger = self.alan["deger"]
        if self.alan["tur"] == "secim":
            self.degisken.set(self._gorunen(str(deger)))
            return
        self.degisken.set(bool(deger) if self.alan["tur"] == "evet_hayir" else ("" if deger is None else str(deger)))


class Uygulama:
    def __init__(self, kok: tk.Tk) -> None:
        self.kok = kok
        self.yurutucu = IsYurutucu(arayuz="gui")
        self.video: Path | None = None
        self.baglanti: str | None = None  # https bağlantısı (isteğe bağlı yt-dlp / gallery-dl)
        self.alanlar: list[AyarAlani] = []
        kok.title(f"Dublaj hattı {__version__}")
        kok.minsize(820, 600)
        kok.protocol("WM_DELETE_WINDOW", self.kapat)

        sekmeler = ttk.Notebook(kok)
        sekmeler.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        sekmeler.add(self._onerilen_sekmesi(sekmeler), text="  Önerilen akış  ")
        sekmeler.add(self._gelismis_sekmesi(sekmeler), text="  Gelişmiş  ")
        from dublaj_hatti.gui_isler import IslerSekmesi  # iş geçmişi, sorunlu işler, devam (is_yonetimi)

        self.isler = IslerSekmesi(sekmeler, self.yurutucu, self.degisiklikler)
        sekmeler.add(self.isler.cerceve, text="  İşler  ")
        sekmeler.bind("<<NotebookTabChanged>>",
                      lambda _e: self.isler.yenile() if sekmeler.select() == str(self.isler.cerceve) else None)
        self._ilerleme_alani(kok)
        self.kok.after(1000, self._yokla)

    # --- sekmeler --------------------------------------------------------------------------------------
    def _onerilen_sekmesi(self, ust: ttk.Notebook) -> ttk.Frame:
        cerceve = ttk.Frame(ust, padding=16)
        # Kurulum eksikse ilk açılışta açık uyarı (pencere çizildikten sonra denetlenir; boşsa görünmez).
        self.kurulum_uyari = ttk.Label(cerceve, text="", foreground="#b3261e", wraplength=720, justify="left")
        self.kurulum_uyari.pack(anchor="w")
        self.kok.after(300, self._kurulumu_denetle)
        ttk.Label(cerceve, text="1. Videonu seç", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        ttk.Button(satir, text="Video seç…", command=self.video_sec).pack(side="left")
        self.video_yazi = ttk.Label(satir, text="henüz seçilmedi")
        self.video_yazi.pack(side="left", padx=10)
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=(0, 6))
        ttk.Label(satir, text="ya da bağlantı:").pack(side="left")
        self.baglanti_degisken = tk.StringVar()
        ttk.Entry(satir, textvariable=self.baglanti_degisken, width=52).pack(side="left", padx=6)
        ttk.Button(satir, text="Bağlantıyı kullan", command=self.baglanti_kullan).pack(side="left")
        # Dublaj dili: Gelişmiş'teki genel.hedef_dil alanına bağlanır (_onerilen_dili_bagla); ayrı bir ayar tutulmaz.
        ttk.Label(cerceve, text="2. Dublaj dili", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 0))
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        self.dil_degisken = tk.StringVar()
        self.dil_kutu = ttk.Combobox(satir, textvariable=self.dil_degisken, state="readonly", width=28)
        self.dil_kutu.pack(side="left")
        self.dil_kutu.bind("<<ComboboxSelected>>", self._onerilen_dil_secildi)
        self._dil_eslesme: dict[str, str] = {}
        ttk.Label(cerceve, text="3. Başlat", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 0))
        satir = ttk.Frame(cerceve)
        satir.pack(fill="x", pady=6)
        self.dublajla_dugme = ttk.Button(satir, text=kayit.dublajla_etiketi("tr"), command=lambda: self.baslat("dublaj"),
                                         state="disabled")
        self.dublajla_dugme.pack(side="left")
        self.transkript_dugme = ttk.Button(satir, text="Yalnız altyazı / metin çıkar",
                                           command=lambda: self.baslat("transkript"), state="disabled")
        self.transkript_dugme.pack(side="left", padx=8)
        ttk.Label(cerceve, text=ONERILEN_ACIKLAMA, wraplength=720, foreground="#5d6677",
                  justify="left").pack(anchor="w", pady=(14, 0))
        return cerceve

    def _gelismis_sekmesi(self, ust: ttk.Notebook) -> ttk.Frame:
        dis = ttk.Frame(ust, padding=(8, 8))
        ust_satir = ttk.Frame(dis)
        ust_satir.pack(fill="x")
        ttk.Label(ust_satir, text="Değiştirilen ayarlar mavi görünür ve yalnız bu oturumda geçerlidir; kalıcı "
                  "yapmak için ayarlar/kullanici.toml dosyasına yazın.", foreground="#5d6677").pack(side="left")
        ttk.Button(ust_satir, text="Varsayılana dön", command=self.sifirla).pack(side="right")
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
                ttk.Label(ic, text=bolum.replace("_", " ").capitalize(), font=("Segoe UI", 10, "bold")).grid(
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
                    hedef.secenekleri_degistir(v["izinli"], dict.fromkeys(v["denenmemis"], "denenmedi (uyarı)"))

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
        """Gelişmiş alanındaki değeri ve (ses motoruna göre süzülmüş) seçenekleri Önerilen'e yansıtır, düğmeyi adlandırır."""
        alan = self._dil_alani()
        if alan is None:
            return
        adlar = dict(alan.alan.get("dil_adlari") or {})

        def gorunen(kod: str) -> str:
            ad = adlar.get(kod) or kayit.dil_kendi_adi(kod)
            return f"{ad}  ·  denenmedi" if alan.etiketler.get(kod) else ad

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
        cerceve.pack(fill="x")
        self.durum_yazi = ttk.Label(cerceve, text="Hazır", font=("Segoe UI", 10, "bold"))
        self.durum_yazi.pack(anchor="w")
        self.cubuk = ttk.Progressbar(cerceve, maximum=100)
        self.cubuk.pack(fill="x", pady=4)
        dugmeler = ttk.Frame(cerceve)
        dugmeler.pack(fill="x")
        self.durdur_dugme = ttk.Button(dugmeler, text="Durdur", command=self.yurutucu.durdur, state="disabled")
        self.durdur_dugme.pack(side="left")
        self.oynat_dugme = ttk.Button(dugmeler, text="Videoyu aç", command=self.videoyu_ac, state="disabled")
        self.oynat_dugme.pack(side="left", padx=6)
        self.klasor_dugme = ttk.Button(dugmeler, text="Çıktı klasörünü aç", command=self.klasoru_ac, state="disabled")
        self.klasor_dugme.pack(side="left")
        self.gunluk_dugme = ttk.Button(dugmeler, text="Günlüğü göster", command=self.gunluk_ac_kapa)
        self.gunluk_dugme.pack(side="right")
        self.gunluk = ScrolledText(cerceve, height=10, font=("Consolas", 9), state="disabled")
        self.gunluk_acik = False

    # --- eylemler --------------------------------------------------------------------------------------
    def _kurulumu_denetle(self) -> None:
        try:
            eksik = kurulum_eksikleri()
        except Exception as hata:  # denetim arayüzü hiçbir zaman düşürmez
            eksik = [f"denetlenemedi: {hata}"]
        if eksik:
            self.kurulum_uyari.configure(text=(
                f"Kurulum tamamlanmamış, eksik: {', '.join(eksik)}.\nRepo klasöründeki kur.cmd dosyasına çift tıklayın "
                "(ya da yapay zekâ asistanınıza \"dublaj hattının kurulumunu bitir\" deyin), sonra bu pencereyi yeniden "
                "açın. Ayrıntı: docs/baslarken.md\n"))

    def video_sec(self) -> None:
        yol = filedialog.askopenfilename(title="Video seç", filetypes=VIDEO_TURLERI)
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
                    raise AyarHatasi(f"{alan.alan['anahtar']}: sayı bekleniyor") from hata
        return cikti

    def baglanti_kullan(self) -> None:
        """Bağlantıyı doğrular: türüne göre yalnız gereken isteğe bağlı araç aranır, yoksa kurulum ipucu gösterilir."""
        from dublaj_hatti.kaynak_girdisi import KaynakHatasi, kaynak_dogrula

        try:
            self.baglanti = kaynak_dogrula(self.baglanti_degisken.get())
        except KaynakHatasi as hata:
            messagebox.showerror("Bağlantı kullanılamıyor", str(hata), parent=self.kok)
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
            messagebox.showerror("Başlatılamadı", str(hata), parent=self.kok)
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
        self.gunluk_dugme.configure(text="Günlüğü gizle" if self.gunluk_acik else "Günlüğü göster")

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
        if d["durum"] != "bos":
            dakika, saniye = divmod(int(d["gecen_sn"]), 60)
            self.durum_yazi.configure(text=f"{DURUM_YAZISI[d['durum']]} · %{d['yuzde']} · "
                                           f"{d['bekleme'] or d['asama_adi'] or 'hazırlanıyor'} · "
                                           f"{dakika} dk {saniye} sn" + (f" · iş #{d['is']}" if d["is"] else ""))
            self.cubuk.configure(value=d["yuzde"])
            self.gunluk.configure(state="normal")
            self.gunluk.delete("1.0", "end")
            self.gunluk.insert("end", "\n".join(d["gunluk"]))
            self.gunluk.see("end")
            self.gunluk.configure(state="disabled")
            if d["durum"] == "hata" and not getattr(self, "_hata_gosterildi", False):
                self._hata_gosterildi = True
                messagebox.showerror("İş başarısız", d["hata"] or "ayrıntı günlükte", parent=self.kok)
            if d["durum"] == "calisiyor":
                self._hata_gosterildi = False
        self._dugmeleri_ayarla()
        self.kok.after(1000, self._yokla)

    def kapat(self) -> None:
        if self.yurutucu.calisiyor() and not messagebox.askyesno(
                "Çıkış", "Bir iş sürüyor. Durdurup çıkılsın mı? (Sonra İşler sekmesinden sürdürülebilir.)", parent=self.kok):
            return
        self.yurutucu.kapat()
        self.kok.destroy()


def main(argv: list[str] | None = None) -> int:
    kok = tk.Tk()
    Uygulama(kok)
    kok.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
