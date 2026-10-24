"""Telegram botu (isteğe bağlı, extras `telegram`): kendi bilgisayarınızdaki hattı telefondan sürmek için ince arayüz.

Komutlar: /start, /yardim, /ayarlar (menü), /isler, /sorunlu, /biten, /durum [no], /iptal [no], /kontrol.
İş yönetimi (sorunlu iş devamı, aşamadan yeniden, arşiv) komut satırı, masaüstü ve web ile aynı iş deposundadır.
Video gönderin (ya da https bağlantısı yazın) → iş başlar; ilerleme aynı mesajda güncellenir, bitince video
(sınırın altındaysa) ya da çıktı klasörü bildirilir. Seçimler yalnız bellekte tutulur (diske kişisel veri yazılmaz).
Ağ: yalnız Telegram Bot API'ye giden uzun yoklama (long polling); açık port yok.
Sınırlar: bulut Bot API 20 MB indirme / 50 MB gönderme; `TELEGRAM_YEREL_SUNUCU` ayarlıysa (yerel Bot API sunucusu,
`dubla-telegram sunucu kur`) ikisi de 2000 MB. Alt komutlar: `dubla-telegram sunucu ...`, `dubla-telegram gonder ...`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import is_menuleri, menuler, teslim
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu import yerel_sunucu as ys
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.arka_uc import IsArkaUcu, arka_uc_sec
from dublaj_hatti.bolum_80_arayuz_ve_teslim.telegram_botu.guvenlik import (
    TelegramAyarHatasi,
    baslatma_denetimi,
    gizle,
    yetkili_mi,
)

logger = logging.getLogger("dublaj_hatti.telegram")
KURULUM_IPUCU = "Telegram botu için python-telegram-bot kurulu değil: pip install .[telegram]"
INDIRME_SINIRI = ys.BULUT_INDIRME_SINIRI  # bulut Bot API; yerel sunucuda ys.indirme_siniri(adres)
GONDERME_SINIRI = ys.BULUT_GONDERME_SINIRI  # bulut Bot API; yerel sunucuda ys.gonderme_siniri(adres)
VIDEO_UZANTILARI = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
YOKLAMA_SN = 10
YARDIM = (
    "Video gönderin (bulut Bot API en çok 20 MB, yerel sunucu 2000 MB) ya da https bağlantısı yazın.\n"
    "/ayarlar  seçimleri değiştir (yalnız bu oturum için)\n"
    "/isler  son işler · /durum [no] · /iptal [no]\n"
    "/sorunlu  hata alan / kesilen işler: kaldığı yerden devam, aşamadan yeniden\n"
    "/biten  biten işler: seçilen aşamadan (isterseniz /ayarlar seçimlerinizle) yeniden\n"
    "/kontrol  motorların kurulum durumu\n"
    "Yalnız hakkınız olan ya da izinli içeriği işleyin."
)


def _telegram():
    try:
        import telegram
        import telegram.ext
    except ImportError as hata:
        raise TelegramAyarHatasi(KURULUM_IPUCU) from hata
    return telegram, telegram.ext


def ilerleme_metni(ozet: dict[str, Any]) -> str:
    durum = ozet.get("durum", "")
    satir = f"İş {ozet.get('is_id', '?')}: {durum}"
    if durum == "calisiyor":
        satir += f" · %{ozet.get('yuzde', 0)} · {ozet.get('asama_adi') or ozet.get('asama') or 'başlıyor'}"
    elif durum == "hata":
        satir += f"\n{gizle(str(ozet.get('hata', '')))[:500]}"
    return satir + f" · {int(float(ozet.get('gecen_sn') or 0))} sn"


def cikti_videolari(ozet: dict[str, Any]) -> list[Path]:
    yollar = [Path(c.get("yol", "")) for c in ozet.get("ciktilar") or []]
    return [y for y in yollar if y.suffix.lower() == ".mp4" and y.is_file()]


class DublajBotu:
    def __init__(self, izinliler: frozenset[int], arka_uc: IsArkaUcu | None = None,
                 girdi_klasoru: Path | None = None, yerel_adres: str | None = None) -> None:
        from dublaj_hatti.is_yurutucu import ayar_formu

        self.yerel_adres = ys.yerel_adres() if yerel_adres is None else yerel_adres

        self.izinliler = izinliler
        self.arka_uc = arka_uc or arka_uc_sec()
        self.ogeler = menuler.menu_ogeleri(ayar_formu())
        self.secimler: dict[int, dict[str, Any]] = {}
        self.izinsiz_istek = 0
        if girdi_klasoru is None:
            from dublaj_hatti.web import cikti_koku

            girdi_klasoru = cikti_koku() / "_telegram_girdileri"
        self.girdi_klasoru = girdi_klasoru

    # --- yardımcılar -------------------------------------------------------------------------------
    def _yetkili(self, update: Any) -> bool:
        kullanici = getattr(update, "effective_user", None)
        if yetkili_mi(getattr(kullanici, "id", None), self.izinliler):
            return True
        self.izinsiz_istek += 1
        return False

    def _klavye(self, dugmeler: list[tuple[str, str]]):
        telegram, _ = _telegram()
        return telegram.InlineKeyboardMarkup([[telegram.InlineKeyboardButton(m, callback_data=v)] for m, v in dugmeler])

    # --- komutlar ----------------------------------------------------------------------------------
    async def start(self, update: Any, context: Any) -> None:
        if self._yetkili(update):
            await update.message.reply_text(YARDIM)

    async def kontrol(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        from dublaj_hatti import kayit

        satirlar = []
        for tur in ("stt", "ceviri", "tts", "ek"):
            durum = kayit.durum(tur)
            satirlar.append(f"{tur}: " + ", ".join(f"{ad}{' ✓' if ok else ''}" for ad, ok in durum.items()))
        await update.message.reply_text("\n".join(satirlar)[:4000])

    async def ayarlar(self, update: Any, context: Any) -> None:
        if self._yetkili(update):
            await update.message.reply_text("Bölüm seçin:", reply_markup=self._klavye(menuler.bolum_dugmeleri(self.ogeler)))

    async def dugme(self, update: Any, context: Any) -> None:
        sorgu = update.callback_query
        if not self._yetkili(update):
            await sorgu.answer()
            return
        await sorgu.answer()
        if is_menuleri.is_menusu_mu(sorgu.data):
            await self._is_menusu(update, context, sorgu)
            return
        kisi = update.effective_user.id
        secim = self.secimler.setdefault(kisi, {})
        tur, deger = menuler.geri_cagirma_coz(sorgu.data, self.ogeler)
        if tur == "bolum":
            await sorgu.edit_message_text(f"{deger}:", reply_markup=self._klavye(
                menuler.anahtar_dugmeleri(self.ogeler, deger, secim) + [("Geri", "s:geri")]))
        elif tur == "anahtar":
            await sorgu.edit_message_text(f"{deger['anahtar']}\n{deger.get('aciklama', '')[:300]}",
                                          reply_markup=self._klavye(menuler.deger_dugmeleri(self.ogeler, deger)))
        elif tur == "deger":
            anahtar, yeni = deger
            deneme = {**secim, anahtar: yeni}
            try:
                from dublaj_hatti.is_yurutucu import ayar_degisiklikleri

                ayar_degisiklikleri(deneme)  # ayar katmanı doğrular (kombinasyon dahil)
            except ValueError as hata:
                await sorgu.edit_message_text(f"Olmadı: {hata}")
                return
            secim[anahtar] = yeni
            await sorgu.edit_message_text(f"{anahtar} = {menuler.deger_metni(yeni)}",
                                          reply_markup=self._klavye(menuler.bolum_dugmeleri(self.ogeler)))
        elif tur == "sifirla" and sorgu.data == "s":
            self.secimler.pop(kisi, None)
            await sorgu.edit_message_text("Seçimler varsayılana döndü.")
        elif sorgu.data == "s:geri":
            await sorgu.edit_message_text("Bölüm seçin:", reply_markup=self._klavye(menuler.bolum_dugmeleri(self.ogeler)))
        else:
            await sorgu.edit_message_text("Menü kapandı.")

    async def isler(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        if self._is_yonetimi_var():
            await self._is_listesi_gonder(update.message, "l")
            return
        liste = self.arka_uc.liste(10)
        await update.message.reply_text("\n".join(ilerleme_metni(o) for o in liste) or "Henüz iş yok.")

    async def sorunlu(self, update: Any, context: Any) -> None:
        if self._yetkili(update):
            await self._is_listesi_gonder(update.message, "s")

    async def biten(self, update: Any, context: Any) -> None:
        if self._yetkili(update):
            await self._is_listesi_gonder(update.message, "b")

    # --- iş yönetimi menüsü (sorunlu / biten işler, devam, yeniden, iptal, arşiv) --------------------------
    def _is_yonetimi_var(self) -> bool:
        return all(hasattr(self.arka_uc, ad) for ad in ("sorunlu", "biten", "secenekler", "devam", "arsivle"))

    def _liste_al(self, tur: str) -> list[dict[str, Any]]:
        sinir = is_menuleri.LISTE_SINIRI[tur]
        return {"s": self.arka_uc.sorunlu, "b": self.arka_uc.biten}.get(tur, self.arka_uc.liste)(sinir)

    async def _is_listesi_gonder(self, mesaj: Any, tur: str) -> None:
        if not self._is_yonetimi_var():
            await mesaj.reply_text("Bu arka uçta iş yönetimi yok.")
            return
        isler = self._liste_al(tur)
        await mesaj.reply_text(is_menuleri.liste_metni(tur, isler),
                               reply_markup=self._klavye(is_menuleri.liste_dugmeleri(tur, isler)))

    async def _is_menusu(self, update: Any, context: Any, sorgu: Any) -> None:
        cozum = is_menuleri.coz(sorgu.data)
        if cozum is None or not self._is_yonetimi_var():
            await sorgu.edit_message_text("Menü kapandı.")
            return
        eylem, no, sira = cozum
        secim = dict(self.secimler.get(update.effective_user.id, {}))
        if no is None:  # liste
            isler = self._liste_al(eylem)
            await sorgu.edit_message_text(is_menuleri.liste_metni(eylem, isler),
                                          reply_markup=self._klavye(is_menuleri.liste_dugmeleri(eylem, isler)))
            return
        try:
            if eylem in ("d", "y", "r", "R"):
                yeni = self.arka_uc.devam(str(no), asama=sira, yeni_is=eylem != "d",
                                          ayarlar=secim if eylem in ("y", "R") else None)
                nasil = "kaldığı yerden" if eylem == "d" else (f"{sira}. aşamadan" if sira else "son geçerli aşamadan")
                await sorgu.edit_message_text(f"İş {yeni} sıraya alındı ({nasil}; kaynak iş #{no}).")
                bilgi = await sorgu.message.reply_text(f"İş {yeni} başlıyor.")
                context.application.create_task(self._izle(context, update.effective_chat.id, bilgi, str(yeni)))
                return
            if eylem == "x":
                tamam = self.arka_uc.iptal(str(no))
                await sorgu.edit_message_text(f"İş #{no} iptal edildi; sonra devam ettirilebilir." if tamam
                                              else f"İş #{no} iptal edilemedi (çalışmıyor ya da başka arayüzde).")
                return
            if eylem == "Z":
                tamam = self.arka_uc.arsivle(str(no))
                await sorgu.edit_message_text(f"İş #{no} arşivlendi (dosyalar duruyor)." if tamam
                                              else f"İş #{no} arşivlenemedi (çalışan iş arşivlenmez).")
                return
            secenek = self.arka_uc.secenekler(str(no))
        except (RuntimeError, ValueError) as hata:  # IsHatasi bir RuntimeError
            await sorgu.edit_message_text(f"Olmadı: {gizle(str(hata))[:500]}")
            return
        if eylem == "a":
            await sorgu.edit_message_text(f"İş #{no}: hangi aşamadan yeniden? (öncesi korunur, yeni iş açılır)",
                                          reply_markup=self._klavye(is_menuleri.asama_dugmeleri(secenek, bool(secim))))
        elif eylem == "z":
            await sorgu.edit_message_text(f"İş #{no} kaydı arşivlensin mi?",
                                          reply_markup=self._klavye(is_menuleri.arsiv_onay_dugmeleri(no)))
        else:  # v
            await sorgu.edit_message_text(is_menuleri.ayrinti_metni(secenek),
                                          reply_markup=self._klavye(is_menuleri.ayrinti_dugmeleri(secenek, bool(secim))))

    async def durum(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        liste = self.arka_uc.liste(1)
        is_id = (context.args or [liste[0]["is_id"] if liste else ""])[0]
        await update.message.reply_text(ilerleme_metni(self.arka_uc.durum(is_id)) if is_id else "Henüz iş yok.")

    async def iptal(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        liste = self.arka_uc.liste(1)
        is_id = (context.args or [liste[0]["is_id"] if liste else ""])[0]
        await update.message.reply_text("İptal edildi." if is_id and self.arka_uc.iptal(is_id) else "Çalışan iş yok.")

    # --- iş başlatma -------------------------------------------------------------------------------
    async def video(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        mesaj = update.message
        dosya = mesaj.video or mesaj.document
        ad = str(getattr(dosya, "file_name", "") or "video.mp4")
        uzanti = Path(ad).suffix.lower() or ".mp4"
        if uzanti not in VIDEO_UZANTILARI:
            await mesaj.reply_text("Yalnız video dosyası (mp4, mkv, mov, webm, avi).")
            return
        if (getattr(dosya, "file_size", 0) or 0) > ys.indirme_siniri(self.yerel_adres):
            await mesaj.reply_text(
                "Dosya 2000 MB üstü: Telegram kabul etmez." if self.yerel_adres else
                "Bulut Bot API 20 MB üstünü indiremez: bilgisayarda arayüzle açın ya da yerel sunucuyu kurun "
                "(dubla-telegram sunucu kur; 2000 MB).")
            return
        self.girdi_klasoru.mkdir(parents=True, exist_ok=True)
        hedef = self.girdi_klasoru / f"{uuid.uuid4().hex}{uzanti}"  # özgün ad diske yazılmaz
        try:
            tg_dosya = await context.bot.get_file(dosya.file_id, read_timeout=1800, connect_timeout=30,
                                                  pool_timeout=60)
            kapsayici_yolu = kapsayici_dosya_yolu(tg_dosya.file_path, context.bot.token) if self.yerel_adres else None
            if kapsayici_yolu:
                await asyncio.to_thread(kapsayicidan_al, kapsayici_yolu, hedef)
            else:
                await tg_dosya.download_to_drive(custom_path=str(hedef), read_timeout=1800, write_timeout=1800,
                                                 connect_timeout=30, pool_timeout=60)
        except Exception as hata:  # indirme hatası işi başlatmaz; kullanıcıya söylenir
            await mesaj.reply_text(f"Video indirilemedi: {gizle(str(hata))[:300]}")
            return
        await self._baslat(update, context, str(hedef))

    async def baglanti(self, update: Any, context: Any) -> None:
        if not self._yetkili(update):
            return
        metin = (update.message.text or "").strip()
        if not metin.startswith("https://") or any(c.isspace() for c in metin):
            await update.message.reply_text(YARDIM)
            return
        await self._baslat(update, context, metin)

    async def _baslat(self, update: Any, context: Any, kaynak: str) -> None:
        secim = dict(self.secimler.get(update.effective_user.id, {}))
        try:
            is_id = self.arka_uc.baslat(kaynak, secim)
        except (RuntimeError, ValueError) as hata:
            await update.message.reply_text(f"Başlatılamadı: {gizle(str(hata))}")
            return
        mesaj = await update.message.reply_text(f"İş {is_id} başladı.")
        context.application.create_task(self._izle(context, update.effective_chat.id, mesaj, is_id))

    async def _izle(self, context: Any, sohbet: int, mesaj: Any, is_id: str) -> None:
        son = ""
        while True:
            await asyncio.sleep(YOKLAMA_SN)
            ozet = self.arka_uc.durum(is_id)
            metin = ilerleme_metni(ozet)
            if metin != son:
                son = metin
                try:
                    await mesaj.edit_text(metin)
                except Exception:  # "message is not modified" vb. — ilerleme gösterimi işi düşürmez
                    logger.debug("ilerleme mesajı güncellenemedi")
            if ozet.get("durum") not in ("calisiyor", "kuyrukta"):
                break
        if ozet.get("durum") != "bitti":
            return
        videolar = cikti_videolari(ozet)
        if not videolar:
            await context.bot.send_message(sohbet, f"İş {is_id} bitti; çıktı klasörüne bakın.")
            return
        video = videolar[0]
        sonuc = await teslim.dosya_gonder(context.bot, sohbet, video, baslik=f"İş {is_id}: {video.name} (AI-dubbed)",
                                          adres=self.yerel_adres)
        if sonuc:
            return
        logger.warning("teslim olmadı: iş %s, durum %s", is_id, sonuc.durum)
        await context.bot.send_message(sohbet, f"İş {is_id} bitti ama dosya gönderilmedi ({sonuc.durum}): "
                                               f"{sonuc.neden[:600]}\nDosya bilgisayarda: {video.parent}")

    # --- kurulum -----------------------------------------------------------------------------------
    def uygulama(self, belirtec: str):
        telegram, ext = _telegram()
        app = uygulama_kurucu(ext.Application.builder().token(belirtec), self.yerel_adres).build()
        app.add_handler(ext.CommandHandler(["start", "yardim", "help"], self.start))
        app.add_handler(ext.CommandHandler("ayarlar", self.ayarlar))
        app.add_handler(ext.CommandHandler("isler", self.isler))
        app.add_handler(ext.CommandHandler("sorunlu", self.sorunlu))
        app.add_handler(ext.CommandHandler("biten", self.biten))
        app.add_handler(ext.CommandHandler("durum", self.durum))
        app.add_handler(ext.CommandHandler("iptal", self.iptal))
        app.add_handler(ext.CommandHandler("kontrol", self.kontrol))
        app.add_handler(ext.CallbackQueryHandler(self.dugme))
        app.add_handler(ext.MessageHandler(ext.filters.VIDEO | ext.filters.Document.VIDEO, self.video))
        app.add_handler(ext.MessageHandler(ext.filters.TEXT & ~ext.filters.COMMAND, self.baglanti))
        return app


def uygulama_kurucu(kurucu: Any, adres: str) -> Any:
    """Yerel sunucu varsa bütün istekler (dosya indirme dahil) ona gider; süreler büyük dosyaya göre geniş."""
    kurucu = kurucu.read_timeout(300).write_timeout(600).connect_timeout(30).pool_timeout(60)
    if adres:
        kurucu = kurucu.base_url(f"{adres}/bot").base_file_url(f"{adres}/file/bot").local_mode(True)
    return kurucu


def kapsayici_dosya_yolu(file_path: str | None, belirtec: str) -> str | None:
    """Yerel kipte getFile mutlak yol döndürür; sunucu Docker kapsayıcısındaysa bu yol kapsayıcının içindedir (bu
    bilgisayarda yoktur). Yalnız bu botun kendi klasöründeki yol kabul edilir (yol kaçışı olmaz)."""
    from urllib.parse import unquote, urlparse

    if not file_path:
        return None
    yol = unquote(urlparse(str(file_path)).path)
    isaret = f"/file/bot{belirtec}"
    if isaret in yol:
        yol = yol.split(isaret, 1)[1]
    yol = "/" + yol.lstrip("/")
    kok = ys.KAPSAYICI_IS_KLASORU.rstrip("/") + "/"
    if not yol.startswith(kok) or Path(yol).exists():
        return None
    parcalar = yol[len(kok):].split("/")
    if not parcalar or parcalar[0] != belirtec or ".." in parcalar:
        return None
    return kok + "/".join(parcalar)


def kapsayicidan_al(kapsayici_yolu: str, hedef: Path) -> None:
    """Sunucunun indirdiği dosyayı kapsayıcıdan kopyalar, sonra kapsayıcıdaki kopyayı siler (disk büyümesin)."""
    ad = os.environ.get(ys.KAPSAYICI_DEGISKENI) or ys.KAPSAYICI
    sonuc = ys._docker("cp", f"{ad}:{kapsayici_yolu}", str(hedef), sure=1800)
    if sonuc.returncode != 0:
        raise RuntimeError(f"kapsayıcıdan kopyalanamadı: {gizle(sonuc.stderr.strip())[:200]}")
    ys._docker("exec", ad, "rm", "-f", kapsayici_yolu, sure=60)


def _tek_ornek_kilidi(klasor: Path) -> Path:
    """Aynı belirteçle iki bot = Telegram 409 çakışması; ikinci başlatma reddedilir (bayat kilit temizlenir)."""
    import psutil

    klasor.mkdir(parents=True, exist_ok=True)
    kilit = klasor / "telegram_botu.kilit"
    if kilit.exists():
        try:
            eski = int(kilit.read_text(encoding="ascii").strip() or 0)
        except (OSError, ValueError):
            eski = 0
        if eski and psutil.pid_exists(eski):
            raise TelegramAyarHatasi(f"bot zaten çalışıyor (süreç {eski})")
        kilit.unlink(missing_ok=True)
    with open(kilit, "x", encoding="ascii") as dosya:
        dosya.write(str(os.getpid()))
    return kilit


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "sunucu":
        return ys.main(argv[1:])
    if argv and argv[0] == "gonder":
        return teslim.main(argv[1:])
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # istek adresleri belirteci içerir: günlüğe yazılmaz
    try:
        _telegram()
        belirtec, izinliler = baslatma_denetimi()
        adres = ys.yerel_adres()
        if adres and not ys.hazir_bekle(adres, belirtec, sure=10):
            raise TelegramAyarHatasi(f"yerel sunucu {adres} getMe cevabı vermiyor: dubla-telegram sunucu baslat "
                                     f"(ya da .env'de {ys.ADRES_DEGISKENI}= boş bırakıp bulut uç noktasına dönün)")
        if not adres:
            logger.info("Bulut Bot API: 50 MB üstü sonuçlar gönderilemez (2 GB: dubla-telegram sunucu kur).")
        bot = DublajBotu(izinliler, yerel_adres=adres)
        kilit = _tek_ornek_kilidi(bot.girdi_klasoru)
    except TelegramAyarHatasi as hata:
        print(f"Telegram botu başlatılamadı: {hata}")
        return 2
    try:
        logger.info("Telegram botu başladı (%d izinli kullanıcı). Durdurmak için Ctrl+C.", len(izinliler))
        bot.uygulama(belirtec).run_polling()
    finally:
        kilit.unlink(missing_ok=True)
        logger.info("Telegram botu kapandı; izinsiz istek sayısı: %d", bot.izinsiz_istek)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
