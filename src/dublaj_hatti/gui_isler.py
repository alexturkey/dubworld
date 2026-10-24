"""Masaüstü arayüzün "İşler" sekmesi: iş geçmişi, sorunlu işler, devam / aşamadan yeniden çalıştırma,
çıktı klasörünü açma, arşivleme (yalnız iş kaydı; dosyalar silinmez).

Bütün mantık `IsYurutucu` (is_yonetimi) içindedir; bu sekme yalnız gösterir ve düğmeleri bağlar.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

from dublaj_hatti.is_yurutucu import IsYurutucu, cikti_klasoru_ac

SUTUNLAR = (("is", "#", 50), ("durum_adi", "Durum", 110), ("komut", "İş", 80), ("kaynak_adi", "Kaynak", 220),
            ("asama", "Son / kesildiği aşama", 200), ("zaman", "Zaman", 140))


class IslerSekmesi:
    def __init__(self, ust: ttk.Notebook, yurutucu: IsYurutucu,
                 degisiklikler: Callable[[], dict[str, Any]] | None = None) -> None:
        self.yurutucu = yurutucu
        self.degisiklikler = degisiklikler or (lambda: {})
        self.kayitlar: dict[str, dict[str, Any]] = {}
        self.cerceve = ttk.Frame(ust, padding=(8, 8))
        ust_satir = ttk.Frame(self.cerceve)
        ust_satir.pack(fill="x")
        ttk.Button(ust_satir, text="Yenile", command=self.yenile).pack(side="left")
        self.yalniz_sorunlu = tk.BooleanVar(value=False)
        ttk.Checkbutton(ust_satir, text="Yalnız sorunlu", variable=self.yalniz_sorunlu,
                        command=self.yenile).pack(side="left", padx=8)
        self.arsiv = tk.BooleanVar(value=False)
        ttk.Checkbutton(ust_satir, text="Arşivi de göster", variable=self.arsiv, command=self.yenile).pack(side="left")
        ttk.Label(ust_satir, text="Hata alan ya da kesilen iş kaldığı aşamadan sürer; aşamadan yeniden çalıştırma "
                  "kaynak işi değiştirmez.", foreground="#5d6677").pack(side="left", padx=12)

        self.agac = ttk.Treeview(self.cerceve, columns=[s[0] for s in SUTUNLAR], show="headings", height=12,
                                 selectmode="browse")
        for anahtar, baslik, genislik in SUTUNLAR:
            self.agac.heading(anahtar, text=baslik)
            self.agac.column(anahtar, width=genislik, stretch=anahtar in ("kaynak_adi", "asama"))
        self.agac.tag_configure("sorunlu", foreground="#b42318")
        self.agac.tag_configure("bitti", foreground="#5d6677")
        self.agac.pack(fill="both", expand=True, pady=(8, 4))
        self.agac.bind("<<TreeviewSelect>>", lambda _e: self._secim_degisti())

        self.ayrinti = ttk.Label(self.cerceve, text="", wraplength=760, foreground="#5d6677", justify="left")
        self.ayrinti.pack(anchor="w", fill="x")
        dugmeler = ttk.Frame(self.cerceve)
        dugmeler.pack(fill="x", pady=(6, 0))
        self.devam_dugme = ttk.Button(dugmeler, text="Devam et", command=self.devam_et, state="disabled")
        self.devam_dugme.pack(side="left")
        ttk.Label(dugmeler, text="  Aşamadan:").pack(side="left")
        self.asama = tk.StringVar()
        self.asama_kutu = ttk.Combobox(dugmeler, textvariable=self.asama, state="disabled", width=28)
        self.asama_kutu.pack(side="left", padx=4)
        self.gelismis = tk.BooleanVar(value=False)
        ttk.Checkbutton(dugmeler, text="Gelişmiş ayarlarla", variable=self.gelismis).pack(side="left")
        self.yeniden_dugme = ttk.Button(dugmeler, text="Yeni işe kopyalayıp çalıştır", command=self.yeniden_calistir,
                                        state="disabled")
        self.yeniden_dugme.pack(side="left", padx=4)
        self.klasor_dugme = ttk.Button(dugmeler, text="Klasörü aç", command=self.klasor_ac, state="disabled")
        self.klasor_dugme.pack(side="right")
        self.arsiv_dugme = ttk.Button(dugmeler, text="Sil (kaydı arşivle)", command=self.arsivle, state="disabled")
        self.arsiv_dugme.pack(side="right", padx=4)
        self._asama_kimlikleri: dict[str, str] = {}

    # ---- veri --------------------------------------------------------------------------------------------
    def yenile(self) -> None:
        secili = self.secili_no()
        if self.yalniz_sorunlu.get():
            isler = self.yurutucu.sorunlu(10)
        else:
            isler = self.yurutucu.isler(200, arsiv_dahil=self.arsiv.get())
        self.agac.delete(*self.agac.get_children())
        self.kayitlar.clear()
        for o in isler:
            sorunlu = o["durum"] in ("failed", "cancelled")
            asama = (f"✗ {o['basarisiz_asama_adi'] or '-'}" if sorunlu else o["son_asama_adi"]) or ""
            satir = (o["is"], o["durum_adi"], o["komut"], o["kaynak_adi"] + (f"  (← #{o['ebeveyn']})" if o["ebeveyn"] else ""),
                     asama, o["bitti"] or o["basladi"] or o["eklendi"] or "")
            kimlik = str(o["is"])
            self.kayitlar[kimlik] = o
            self.agac.insert("", "end", iid=kimlik, values=satir,
                             tags=("sorunlu",) if sorunlu else (("bitti",) if o["durum"] == "completed" else ()))
        if secili is not None and str(secili) in self.kayitlar:
            self.agac.selection_set(str(secili))
        self._secim_degisti()

    def secili_no(self) -> int | None:
        secim = self.agac.selection()
        return int(secim[0]) if secim else None

    def _secim_degisti(self) -> None:
        no = self.secili_no()
        o = self.kayitlar.get(str(no)) if no is not None else None
        hepsi = (self.devam_dugme, self.yeniden_dugme, self.klasor_dugme, self.arsiv_dugme)
        for d in hepsi:
            d.configure(state="disabled")
        self.asama_kutu.configure(state="disabled", values=[])
        self.asama.set("")
        if not o:
            self.ayrinti.configure(text="")
            return
        try:
            secenek = self.yurutucu.secenekler(int(no))  # type: ignore[arg-type]
        except RuntimeError as hata:
            self.ayrinti.configure(text=str(hata))
            return
        sorunlu = o["durum"] in ("failed", "cancelled")
        etkin = o["durum"] in ("queued", "deferred", "preparing", "processing")
        metin = [f"İş #{o['is']} · {o['durum_adi']} · {o['kaynak_adi']}"]
        if o["hata"]:
            metin.append(f"Hata: {o['hata'][:300]}")
        if secenek["devam_secenekleri"]:
            metin.append(f"Korunan son aşama: {secenek['devam_secenekleri'][-1]['ad']}")
        elif o["komut"] == "dubla" and not etkin:
            metin.append("Korunabilecek checkpoint yok; baştan çalıştırın.")
        self.ayrinti.configure(text="\n".join(metin))
        if sorunlu and secenek["devam_secenekleri"]:
            self.devam_dugme.configure(state="normal")
        yeniden = secenek["yeniden_calistir"] if not etkin else []
        if yeniden:
            self._asama_kimlikleri = {s["ad"]: s["restart_stage_id"] for s in yeniden}
            self.asama_kutu.configure(state="readonly", values=list(self._asama_kimlikleri))
            self.asama.set(yeniden[-1]["ad"])
            self.yeniden_dugme.configure(state="normal")
        if o["klasor"]:
            self.klasor_dugme.configure(state="normal")
        if not etkin and not o["arsiv"]:
            self.arsiv_dugme.configure(state="normal")

    # ---- eylemler ----------------------------------------------------------------------------------------
    def _dene(self, islev: Callable[[], Any], baslik: str) -> Any:
        try:
            return islev()
        except (RuntimeError, ValueError) as hata:
            messagebox.showerror(baslik, str(hata), parent=self.cerceve)
            return None

    def devam_et(self) -> None:
        no = self.secili_no()
        if no is not None and self._dene(lambda: self.yurutucu.devam(no), "Devam edilemedi") is not None:
            self.yenile()

    def yeniden_calistir(self) -> None:
        no = self.secili_no()
        asama = self._asama_kimlikleri.get(self.asama.get())
        if no is None or not asama:
            return
        ifadeler = []
        if self.gelismis.get():
            for anahtar, deger in self.degisiklikler().items():
                if anahtar == "genel.is_turu":
                    continue
                ifadeler.append(f"{anahtar}={('true' if deger else 'false') if isinstance(deger, bool) else deger}")
        if self._dene(lambda: self.yurutucu.devam(no, asama=asama, yeni_is=True, ayar_ifadeleri=ifadeler),
                      "Yeniden çalıştırılamadı") is not None:
            self.yenile()

    def klasor_ac(self) -> None:
        o = self.kayitlar.get(str(self.secili_no()))
        if o and o["klasor"]:
            cikti_klasoru_ac(o["klasor"])

    def arsivle(self) -> None:
        no = self.secili_no()
        if no is None:
            return
        if not messagebox.askyesno("Arşivle", f"İş #{no} kaydı listeden kaldırılsın mı? İş klasörü ve çıktılar "
                                   "silinmez; 'Arşivi de göster' ile geri görünür.", parent=self.cerceve):
            return
        if not self.yurutucu.arsivle(no):
            messagebox.showerror("Arşivlenemedi", "iş bulunamadı ya da hâlâ etkin", parent=self.cerceve)
        self.yenile()
