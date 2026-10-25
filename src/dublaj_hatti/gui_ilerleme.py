"""Masaüstü ilerleme panosu: duraklı yol, akan çizgili çubuk, kronometre, kalan süre ve "şimdi ne oluyor" satırları.

Veri `IsDurumu.ozet()`ten gelir (duraklar, anlati, kalan_sn; dilden bağımsız); yazılar arayüz dilinde. Web'deki
ilerleme bölümünün eşi (web_statik/app.js `durumCiz`). Windows'ta "animasyonları göster" kapalıysa çizgiler akmaz.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Any

from dublaj_hatti import arayuz_dili
from dublaj_hatti.arayuz_dili import t

RENK = {"ana": "#2457c5", "tamam": "#1a7f37", "gri": "#c9ced6", "soluk": "#5d6677", "yazi": "#1d2330"}
YOL_Y, CUBUK_Y, CUBUK_H, YARICAP = 30, 92, 18, 21
SERIT, ADIM_MS = 28, 80


def hareket_az() -> bool:
    """Windows'ta "Windows'da animasyonları göster" kapalı mı (SPI_GETCLIENTAREAANIMATION)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        acik = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(acik), 0)
        return not acik.value
    except (AttributeError, OSError):
        return False


def saat_yaz(sn: float) -> str:
    """Kronometre: 3:07, 1:02:45 (her dilde aynı)."""
    sn = max(0, int(sn))
    s, d, n = sn // 3600, sn // 60 % 60, sn % 60
    return f"{s}:{d:02d}:{n:02d}" if s else f"{d}:{n:02d}"


def kalan_yaz(sn: int | None) -> str:
    if sn is None:
        return ""
    return t("ilerleme.kalan_az") if sn < 60 else t("ilerleme.kalan", None, dk=round(sn / 60))


def anlati_yaz(satir: dict[str, Any]) -> str:
    asama = satir.get("asama")
    if asama:
        return t(f"anlati.{satir['anahtar']}", None, asama=t(f"asama.{asama}") if arayuz_dili.var_mi(
            f"asama.{asama}", "tr") else asama)
    return t(f"anlati.{satir['anahtar']}")


def _simge(metin: str) -> str:
    return metin.replace("️", "")  # Tk değişken seçiciyi kutu olarak çizebilir


class IlerlemePanosu:
    def __init__(self, ust: ttk.Frame) -> None:
        self.ust = ust
        self.hareket = not hareket_az()
        bas = ttk.Frame(ust)
        bas.pack(fill="x")
        self.baslik = ttk.Label(bas, text=t("ilerleme.hazir"), font=("Segoe UI", 12, "bold"))
        self.baslik.pack(side="left")
        self.yuzde = ttk.Label(bas, text="", font=("Segoe UI", 20, "bold"), foreground=RENK["ana"])
        self.yuzde.pack(side="right")
        zemin = ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
        self.tuval = tk.Canvas(ust, height=CUBUK_Y + CUBUK_H + 4, highlightthickness=0, background=zemin)
        self.tuval.pack(fill="x", pady=(2, 0))
        self.tuval.bind("<Configure>", lambda _o: self._ciz())
        saat = ttk.Frame(ust)
        saat.pack(fill="x")
        self.kronometre = ttk.Label(saat, text="", font=("Segoe UI", 13, "bold"))
        self.kronometre.pack(side="left")
        self.kalan = ttk.Label(saat, text="", foreground=RENK["soluk"])
        self.kalan.pack(side="left", padx=10)
        self.ek = ttk.Label(saat, text="", foreground=RENK["soluk"])
        self.ek.pack(side="right")
        ttk.Label(ust, text=t("ilerleme.ne_oluyor"), font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 0))
        self.pano = tk.Text(ust, height=4, wrap="word", font=("Segoe UI", 11), relief="flat", padx=8, pady=6,
                            background="#ffffff", state="disabled", cursor="arrow")
        self.pano.pack(fill="x", pady=(2, 6))
        self.pano.tag_configure("zaman", foreground=RENK["soluk"])
        self.pano.tag_configure("eski", foreground=RENK["soluk"])
        self.pano.tag_configure("son", foreground=RENK["yazi"], font=("Segoe UI", 11, "bold"))
        self.veri: dict[str, Any] = {"durum": "bos", "duraklar": [], "yuzde": 0}
        self._kaydirma = 0
        self._son_anlati: list[dict[str, Any]] | None = None
        self._saat_an = 0.0

    # --- veri --------------------------------------------------------------------------------------------
    def guncelle(self, d: dict[str, Any], durum_yazisi: str) -> None:
        self.veri = d
        calisiyor = d["durum"] == "calisiyor"
        self.baslik.configure(text=durum_yazisi or t("ilerleme.hazir"))
        if d["durum"] == "bos":
            self.yuzde.configure(text="")
            self.kronometre.configure(text="")
        else:
            yuzde = t("ilerleme.yuzde", None, yuzde=d["yuzde"])
            self.yuzde.configure(text=("🎉 " + yuzde) if d["durum"] == "bitti" else yuzde,
                                 foreground=RENK["tamam"] if d["durum"] == "bitti" else RENK["ana"])
            self.kronometre.configure(text="⏱ " + saat_yaz(d.get("gecen_sn", 0)))
        self.kalan.configure(text=kalan_yaz(d.get("kalan_sn")) if calisiyor else "")
        parcalar = [d.get("bekleme") or ""] + ([t("ilerleme.is_no", None, no=d["is"])] if d.get("is") else [])
        self.ek.configure(text=" · ".join(p for p in parcalar if p))
        self._pano_yaz(d.get("anlati") or [])
        self._ciz()

    def _pano_yaz(self, satirlar: list[dict[str, Any]]) -> None:
        if satirlar == self._son_anlati:
            return
        self._son_anlati = list(satirlar)
        self.pano.configure(state="normal")
        self.pano.delete("1.0", "end")
        for i, s in enumerate(satirlar):
            son = i == len(satirlar) - 1
            self.pano.insert("end", saat_yaz(s.get("sn", 0)).rjust(6) + "  ", "zaman")
            self.pano.insert("end", _simge(anlati_yaz(s)) + ("" if son else "\n"), "son" if son else "eski")
        self.pano.see("end")
        self.pano.configure(state="disabled")

    # --- çizim -------------------------------------------------------------------------------------------
    def _ciz(self) -> None:
        tv = self.tuval
        tv.delete("all")
        genislik = max(tv.winfo_width(), 200)
        duraklar = self.veri.get("duraklar") or []
        n = len(duraklar)
        if n:
            adim = genislik / n
            merkez = [adim * (i + 0.5) for i in range(n)]
            for i in range(1, n):
                renk = RENK["tamam"] if duraklar[i]["durum"] != "bekliyor" else RENK["gri"]
                tv.create_line(merkez[i - 1] + YARICAP, YOL_Y, merkez[i] - YARICAP, YOL_Y, fill=renk, width=3)
            for x, o in zip(merkez, duraklar):
                bitti, suruyor = o["durum"] == "bitti", o["durum"] == "suruyor"
                cerceve = RENK["tamam"] if bitti else RENK["ana"] if suruyor else RENK["gri"]
                r = YARICAP + (2 if suruyor else 0)
                tv.create_oval(x - r, YOL_Y - r, x + r, YOL_Y + r, outline=cerceve, width=3,
                               fill=RENK["tamam"] if bitti else "#ffffff")
                tv.create_text(x, YOL_Y, text="✓" if bitti else _simge(o["simge"]),
                               font=("Segoe UI Emoji", 15, "bold" if bitti else "normal"),
                               fill="#ffffff" if bitti else RENK["yazi"])
                tv.create_text(x, YOL_Y + YARICAP + 14, text=t(f"durak.{o['id']}"), width=max(adim - 6, 40),
                               font=("Segoe UI", 9, "bold" if suruyor else "normal"),
                               fill=RENK["yazi"] if suruyor else RENK["soluk"], justify="center")
        self._cubuk_ciz(genislik)

    def _cubuk_ciz(self, genislik: int) -> None:
        tv = self.tuval
        tv.delete("cubuk")
        x0, x1, y0 = 6, genislik - 6, CUBUK_Y
        tv.create_rectangle(x0, y0, x1, y0 + CUBUK_H, fill=RENK["gri"], width=0, tags="cubuk")
        dolu = x0 + (x1 - x0) * self.veri.get("yuzde", 0) / 100
        if dolu <= x0:
            return
        bitti = self.veri["durum"] == "bitti"
        tv.create_rectangle(x0, y0, dolu, y0 + CUBUK_H, fill=RENK["tamam"] if bitti else RENK["ana"], width=0,
                            tags="cubuk")
        if self.veri["durum"] != "calisiyor":
            return
        renk = "#4f7ad6"  # ana rengin açığı: çizgi
        x = x0 - SERIT + self._kaydirma
        while x < dolu:
            nokta = [x, y0 + CUBUK_H, x + SERIT / 2, y0 + CUBUK_H, x + SERIT / 2 + CUBUK_H, y0, x + CUBUK_H, y0]
            nokta = [min(max(v, x0), dolu) if i % 2 == 0 else v for i, v in enumerate(nokta)]
            tv.create_polygon(nokta, fill=renk, width=0, tags="cubuk")
            x += SERIT

    def adim(self) -> None:
        """Animasyon adımı (çağıran ADIM_MS'de bir): çizgiler akar, kronometre saniye saniye ilerler."""
        if self.veri.get("durum") != "calisiyor":
            return
        if self.hareket:
            self._kaydirma = (self._kaydirma + 2) % SERIT
            self._cubuk_ciz(max(self.tuval.winfo_width(), 200))
