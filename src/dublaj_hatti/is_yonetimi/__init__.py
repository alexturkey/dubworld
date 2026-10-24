"""İş yönetimi çekirdeği (arayüzden bağımsız): iş geçmişi, sorunlu işler, devam / yeniden çalıştırma,
aşama bağımlılığı, açılış kurtarma, bayat iş iptali, kuyruk, soyağacı, seçim denetim kaydı.

Komut satırı (`dubla isler/sorunlu/devam`), masaüstü arayüz, web arayüzü ve Telegram botu aynı SQLite deposunu kullanır.
Depo yeri: `<çıktı kökü>/_is_deposu/isler.sqlite3`; `DUBLAJ_IS_DEPOSU` ortam değişkeni ile değiştirilir.
Tarif: docs/tarifler/devam_ve_sorunlu_isler.md
"""

from dublaj_hatti.is_yonetimi.depo import DURUM_ADLARI, IsDeposu, IsHatasi, is_ozeti, varsayilan_depo_yolu

__all__ = ["DURUM_ADLARI", "IsDeposu", "IsHatasi", "is_ozeti", "telegram_arka_ucu", "varsayilan_depo_yolu"]


def telegram_arka_ucu():
    """Telegram botunun iş arka ucu (sözleşme: telegram_botu/arka_uc.py `IsArkaUcu`); aynı iş deposunu kullanır."""
    from dublaj_hatti.is_yonetimi.telegram_uyarlayici import TelegramArkaUcu

    return TelegramArkaUcu()
