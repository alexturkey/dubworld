"""Arayüzlerin (masaüstü, web) ortak iş yürütücüsü.

İş her zaman `dubla` komut satırının ayrı bir süreci olarak çalışır (pencere açmadan); arayüz yalnız
`--olaylar-json` satırlarını ve günlüğü okur. İşler iş deposunda (is_yonetimi, SQLite) kuyruklanır ve aynı anda
tek iş çalışır; GPU'yu başka bir süreç kullanıyorsa alt süreç makine geneli kaynak kilidinde sırasını bekler.
Masaüstü, web ve komut satırı aynı geçmişi, sorunlu işleri ve devam seçeneklerini görür.
Kabuk (shell) kullanılmaz; bütün değerler argüman listesi olarak geçer.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dublaj_hatti import arayuz_dili
from dublaj_hatti.bolum_00_omurga.core.asama_sozlesmesi import PIPELINE_STAGES
from dublaj_hatti.is_yonetimi.asamalar import ASAMA_ADLARI
from dublaj_hatti.is_yonetimi.depo import IsDeposu, IsHatasi, is_ozeti
from dublaj_hatti.yapilandirma import SEMA, ayarlari_yukle, esleme_metni, form_ek_bilgisi

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
BOSTA_YOKLAMA_SN = 2.0  # kuyruk boşken bekleme; yeni iş eklenince olayla hemen uyanır (boşta ~%0 işlemci)
__all__ = ["ARAYUZ_DISI_AYARLAR", "ASAMA_ADLARI", "FORM_DISI_AYARLAR", "IsDurumu", "IsYurutucu", "arayuz_ayari_denetle", "ayar_degisiklikleri",
           "ayar_formu", "cikti_klasoru_ac"]
# Arayüzden (masaüstü, web, Telegram) değiştirilemeyen ayarlar: yürütülecek yerel programın yolu. Web belirteci ya da
# bot erişimi olan biri bunları değiştirebilseydi istediği programı çalıştırırdı (SECURITY.md: web belirteci = yerel
# komut yürütme yetkisi). Değer yalnız ayar dosyasından (ayarlar/kullanici.toml) ya da ortam değişkeninden gelir.
ARAYUZ_DISI_AYARLAR = frozenset({"ceviri.codex.cli_yolu", "ceviri.claude.cli_yolu"})
# Gelişmiş formunda gösterilmez: arayüzün kendi dil kutusu var (bu oturum); kalıcı değer kullanici.toml'da
FORM_DISI_AYARLAR = frozenset({"genel.arayuz_dili"})


def arayuz_ayari_denetle(anahtar: str) -> None:
    if anahtar in ARAYUZ_DISI_AYARLAR:
        raise ValueError(f"{anahtar} arayüzden değiştirilemez (yerel program yolu); ayarlar/kullanici.toml ya da "
                         "ortam değişkeni kullanın / not settable from the interface")


def ayar_degisiklikleri(yeni: dict[str, Any]) -> list[str]:
    """Varsayılandan farklı değerleri `--ayar a.b=c` listesine çevirir (önce doğrular)."""
    varsayilan = ayarlari_yukle()
    cikti = []
    for anahtar, deger in yeni.items():
        if anahtar not in SEMA:
            raise ValueError(f"bilinmeyen ayar: {anahtar}")
        arayuz_ayari_denetle(anahtar)
        if SEMA[anahtar] is dict:  # konuşmacı → ses eşlemesi: sözlük ya da "SPEAKER_00:M2, ..." metni
            if isinstance(deger, str):
                from dublaj_hatti.yapilandirma import _metin_degeri_coz

                deger = _metin_degeri_coz(anahtar, deger)
            if not isinstance(deger, dict):
                raise ValueError(f"{anahtar} bir eşleme olmalı")
            deger = {str(k): str(v) for k, v in deger.items()}
        if deger == varsayilan.get(anahtar):
            continue
        if isinstance(deger, dict):
            metin = esleme_metni(deger)
        else:
            metin = ("true" if deger else "false") if isinstance(deger, bool) else str(deger)
        if any(c in metin for c in "\r\n\x00"):
            raise ValueError(f"geçersiz karakter: {anahtar}")
        cikti.append(f"{anahtar}={metin}")
    ayarlari_yukle(ustune=cikti)  # tümü birlikte geçerli mi
    return cikti


@dataclass
class IsDurumu:
    durum: str = "bos"  # bos | calisiyor | bitti | hata | durduruldu
    kaynak: str = ""
    is_no: int = 0
    bekleme: str = ""  # "gpu meşgul: ..." (makine geneli kaynak kilidi)
    baslangic: float = 0.0
    bitis: float = 0.0
    asama: str = ""
    tamamlanan: list[str] = field(default_factory=list)
    sonuc: dict[str, Any] = field(default_factory=dict)
    hata: str = ""
    secimler: dict[str, Any] = field(default_factory=dict)
    kip: str = "segment_sync"
    ciktilar: list[dict[str, str]] = field(default_factory=list)
    gunluk: deque = field(default_factory=lambda: deque(maxlen=400))

    def ozet(self) -> dict[str, Any]:
        gecen = (self.bitis or time.time()) - self.baslangic if self.baslangic else 0.0
        asamalar = PIPELINE_STAGES.get(self.kip, PIPELINE_STAGES["segment_sync"])
        toplam_agirlik = sum(a[2] for a in asamalar) or 1
        biten = sum(a[2] for a in asamalar if a[0] in self.tamamlanan)
        yuzde = 100 if self.durum == "bitti" else min(99, int(100 * biten / toplam_agirlik))
        return {
            "durum": self.durum, "kaynak": self.kaynak, "asama": self.asama, "is": self.is_no,
            "bekleme": self.bekleme,
            "asama_adi": ASAMA_ADLARI.get(self.asama, self.asama),
            "asamalar": [{"id": a[0], "ad": ASAMA_ADLARI.get(a[0], a[0]),
                          "durum": "bitti" if a[0] in self.tamamlanan else ("suruyor" if a[0] == self.asama else "bekliyor")}
                         for a in asamalar],
            "yuzde": yuzde, "ciktilar": self.ciktilar,
            "gecen_sn": round(gecen, 1), "sonuc": self.sonuc, "hata": self.hata, "secimler": self.secimler,
            "gunluk": list(self.gunluk)[-80:],
        }


class IsYurutucu:
    """Kuyruklu iş yürütücü: her iş iş deposuna yazılır ve `dubla is-calistir <no>` alt süreciyle sırayla çalışır."""

    def __init__(self, arayuz: str = "gui", depo: IsDeposu | None = None, kuyruk_isle: bool = True) -> None:
        self.arayuz = arayuz
        self.durum = IsDurumu()
        self._surec: subprocess.Popen | None = None
        self._kilit = threading.Lock()
        self._uyandir = threading.Event()
        self._kapat = threading.Event()
        if depo is None:
            from dublaj_hatti.is_yonetimi.calistirici import depo_ac

            depo = depo_ac(ayarlari_yukle())
        self.depo = depo
        self.kurtarilan = self.depo.acilista_kurtar()  # süreci ölmüş yarım işler → sorunlu (devam edilebilir)
        self._isci: threading.Thread | None = None
        if kuyruk_isle:
            self._isci = threading.Thread(target=self._kuyruk_dongusu, name="is-kuyrugu", daemon=True)
            self._isci.start()

    def calisiyor(self) -> bool:
        return self._surec is not None and self._surec.poll() is None

    # ---- iş ekleme ---------------------------------------------------------------------------------------
    def baslat(self, kaynak: str, ayarlar: dict[str, Any], komut: str = "dubla", bicim: str | None = None) -> int:
        """Yeni işi doğrulayıp kuyruğa ekler; iş numarasını döndürür."""
        ifadeler = ayar_degisiklikleri(ayarlar)
        etkin = ayarlari_yukle(ustune=ifadeler)
        if komut == "transkript":
            bicim = bicim or str(etkin.get("genel.transkript_bicimi") or "srt")
        job_id = self.depo.is_ekle(kaynak, etkin, "transkript" if komut == "transkript" else "dubla", self.arayuz,
                                   ifadeler=ifadeler, transkript_bicimi=bicim or "")
        self._uyandir.set()
        return job_id

    def devam(self, job_id: int, asama: str | None = None, yeni_is: bool = False,
              ayar_ifadeleri: list[str] | None = None) -> int:
        """Sorunlu ya da biten işi sürdürür: aşama/ayar verilirse ya da iş bittiyse yeni işe kopyalar, yoksa yerinde."""
        for ifade in ayar_ifadeleri or []:
            arayuz_ayari_denetle(str(ifade).split("=", 1)[0].strip())
        kayit = self.depo.getir(job_id)
        if not kayit:
            raise IsHatasi(f"iş bulunamadı: #{job_id}")
        from dublaj_hatti.is_yonetimi.calistirici import is_ayari
        from dublaj_hatti.is_yonetimi.depo import degisiklikleri_coz

        # Aynı değeri tekrar veren ayar değişiklik sayılmaz: iş yerinde sürer (gereksiz kopya açılmaz).
        degisen = degisiklikleri_coz(is_ayari(kayit), list(ayar_ifadeleri)) if ayar_ifadeleri else {}
        if yeni_is or asama or degisen or kayit["status"] == "completed":
            hedef = self.depo.devam_iste(job_id, list(ayar_ifadeleri or []), asama, arayuz=self.arayuz)
        else:
            hedef = self.depo.yerinde_devam(job_id)
        self._uyandir.set()
        return hedef

    # ---- liste / yönetim ---------------------------------------------------------------------------------
    def isler(self, limit: int = 50, arsiv_dahil: bool = False) -> list[dict[str, Any]]:
        return [is_ozeti(i) for i in self.depo.listele(limit, arsiv_dahil=arsiv_dahil)]

    def sorunlu(self, limit: int = 10) -> list[dict[str, Any]]:
        from dublaj_hatti.is_yonetimi.komutlar import sorunlu_raporu

        return sorunlu_raporu(self.depo, limit)

    def secenekler(self, job_id: int) -> dict[str, Any]:
        kayit = self.depo.getir(job_id)
        if not kayit:
            raise IsHatasi(f"iş bulunamadı: #{job_id}")
        return {**is_ozeti(kayit), "devam_secenekleri": self.depo.devam_secenekleri(kayit),
                "yeniden_calistir": self.depo.yeniden_calistirma_secenekleri(kayit)}

    def arsivle(self, job_id: int) -> bool:
        return self.depo.arsivle(job_id)

    def iptal(self, job_id: int) -> bool:
        return self.depo.iptal(job_id)

    # ---- kuyruk ------------------------------------------------------------------------------------------
    def _kuyruk_dongusu(self) -> None:
        while not self._kapat.is_set():
            self._uyandir.wait(BOSTA_YOKLAMA_SN)
            self._uyandir.clear()
            if self._kapat.is_set():
                return
            with self._kilit:
                if self.calisiyor():
                    continue
                sonraki = self.depo.siradaki(self.arayuz)
                if sonraki:
                    self._alt_sureci_baslat(sonraki)

    def _alt_sureci_baslat(self, kayit: dict[str, Any]) -> None:
        job_id = int(kayit["job_id"])
        argumanlar = [sys.executable, "-m", "dublaj_hatti.cli", "is-calistir", str(job_id), "--olaylar-json"]
        self.durum = IsDurumu(durum="calisiyor", kaynak=str(kayit["source"]), baslangic=time.time(),
                              kip=str(kayit["dubbing_mode"] or "segment_sync"), is_no=job_id)
        self._surec = subprocess.Popen(
            argumanlar, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        )
        threading.Thread(target=self._olaylari_oku, args=(self._surec, self.durum), daemon=True).start()
        threading.Thread(target=self._gunlugu_oku, args=(self._surec, self.durum), daemon=True).start()

    def _olaylari_oku(self, surec: subprocess.Popen, durum: IsDurumu) -> None:
        assert surec.stdout is not None
        for satir in surec.stdout:
            try:
                olay = json.loads(satir)
            except json.JSONDecodeError:
                continue
            tur = olay.get("event")
            if tur == "basladi":
                durum.secimler = olay.get("secimler", {})
            elif tur == "kaynak_bekleniyor":
                durum.bekleme = f"{olay.get('kaynak')} meşgul: " + "; ".join(olay.get("kullananlar") or [])
            elif tur == "stage_started":
                durum.asama = olay.get("stage_id", "")
                durum.bekleme = ""
            elif tur == "artifact_ready":
                durum.ciktilar.append({"tur": str(olay.get("artifact_kind", "")),
                                       "yol": str(olay.get("artifact_path", ""))})
            elif tur in ("stage_completed", "stage_restored", "stage_skipped"):
                if olay.get("stage_id") and olay["stage_id"] not in durum.tamamlanan:
                    durum.tamamlanan.append(olay["stage_id"])
            elif tur == "bitti":
                durum.sonuc = {k: v for k, v in olay.items() if k != "event"}
            elif tur == "hata":
                durum.hata = str(olay.get("mesaj", ""))
        kod = surec.wait()
        durum.bitis = time.time()
        if durum.durum != "durduruldu":
            durum.durum = "bitti" if kod == 0 else "hata"
            if kod != 0 and not durum.hata:
                durum.hata = f"çıkış kodu {kod}; ayrıntı günlükte"
            kayit = self.depo.getir(durum.is_no)
            if kayit and kayit["status"] in ("processing", "preparing"):  # alt süreç kaydı kapatamadan öldüyse
                self.depo.bitir(durum.is_no, "failed", durum.hata)
        self._uyandir.set()  # sıradaki iş

    @staticmethod
    def _gunlugu_oku(surec: subprocess.Popen, durum: IsDurumu) -> None:
        assert surec.stderr is not None
        for satir in surec.stderr:
            durum.gunluk.append(satir.rstrip())

    def durdur(self) -> None:
        """Süren işi durdurur; iş 'iptal / kesildi' olur ve checkpoint'iyle sonra sürdürülebilir."""
        with self._kilit:
            if self.calisiyor() and self._surec is not None:
                self.durum.durum = "durduruldu"
                self._surec.terminate()
                try:
                    self._surec.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._surec.kill()
                kayit = self.depo.getir(self.durum.is_no) if self.durum.is_no else None
                if kayit and kayit["status"] in ("processing", "preparing"):
                    self.depo.bitir(self.durum.is_no, "cancelled", "Kullanıcı durdurdu")

    def kapat(self) -> None:
        """Arayüz kapanırken: süren iş durdurulur, kuyruk iş parçacığı biter (bekleyen işler kayıtta kalır)."""
        self._kapat.set()
        self._uyandir.set()
        self.durdur()


def cikti_klasoru_ac(yol: str) -> None:
    hedef = Path(yol)
    klasor = hedef if hedef.is_dir() else hedef.parent
    if sys.platform == "win32":
        import os

        os.startfile(str(klasor))  # noqa: S606 - kullanıcının kendi tıklamasıyla, yalnız klasör
    else:
        subprocess.Popen(["xdg-open", str(klasor)])


def ayar_aciklamalari() -> dict[str, str]:
    """Gelişmiş sekmesi için her anahtarın açıklaması: `varsayilan.toml` içindeki, anahtardan hemen önceki yorum."""
    metin = (Path(__file__).with_name("varsayilan.toml")).read_text(encoding="utf-8")
    bolum, yorum, cikti = "", list[str](), dict[str, str]()
    for satir in metin.splitlines():
        s = satir.strip()
        if s.startswith("[") and s.endswith("]"):
            bolum, yorum = s.strip("[]").strip(), []
        elif s.startswith("#"):
            yorum.append(s.lstrip("#").strip())
        elif "=" in s and bolum:
            anahtar = f"{bolum}.{s.split('=', 1)[0].strip()}"
            if anahtar in SEMA:
                cikti[anahtar] = " ".join(y for y in yorum if y)
            yorum = []
        elif not s:
            yorum = []
    return cikti


def ayar_formu(dil: str | None = None) -> list[dict[str, Any]]:
    """Arayüzlerin Gelişmiş sekmesi: anahtar, bölüm, tür, seçenekler, geçerli değer, açıklama (SEMA sırası).

    Açıklama arayüz dilindedir (`dil`; yoksa seçili arayüz dili): Türkçenin tek kaynağı `varsayilan.toml`
    yorumlarıdır, öbür diller `arayuz_dilleri/<dil>.json` içindeki `ayar.<anahtar>` (eksikse İngilizce, o da yoksa Türkçe).
    """
    dil = dil or arayuz_dili.secili()
    gecerli = ayarlari_yukle()
    aciklama = ayar_aciklamalari()
    ek = form_ek_bilgisi(dil)  # donanım etiketleri, hedef dil süzgeci, konuşmacı başına ses seçenekleri (yapilandirma)
    form = []
    for anahtar, kural in SEMA.items():
        if anahtar in ARAYUZ_DISI_AYARLAR or anahtar in FORM_DISI_AYARLAR:
            continue
        deger = gecerli.get(anahtar)
        if kural is dict:  # "esleme": metin kutusu "SPEAKER_00:M2, SPEAKER_01:F1"
            tur, secenekler, deger = "esleme", [], esleme_metni(deger or {})
        elif isinstance(kural, list):
            tur, secenekler = "secim", list(kural)
        else:
            tur, secenekler = {bool: "evet_hayir", int: "tam_sayi", float: "ondalik"}.get(kural, "metin"), []
        form.append({"anahtar": anahtar, "bolum": anahtar.split(".")[0], "tur": tur, "secenekler": secenekler,
                     "deger": deger, "aciklama": _aciklama(anahtar, dil, aciklama), **ek.get(anahtar, {})})
    return form


def _aciklama(anahtar: str, dil: str, toml_yorumlari: dict[str, str]) -> str:
    sozluk_aciklamasi = arayuz_dili.sozluk(dil).get(f"ayar.{anahtar}")
    if dil == "tr":
        return toml_yorumlari.get(anahtar) or sozluk_aciklamasi or ""
    return sozluk_aciklamasi or arayuz_dili.sozluk("en").get(f"ayar.{anahtar}") or toml_yorumlari.get(anahtar, "")
