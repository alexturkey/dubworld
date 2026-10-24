<!--
Chinese target appendix. Sources: standard Mandarin numeral reading (years read digit by digit, 万 unit) and
full-width punctuation conventions. The language code is normalised to "zh", so the script variant is not
known; Simplified Chinese is the default. Status: not yet validated in production dubbing.
-->

## genel
Çince için ek kurallar:
- İş bilgisinde başka bir varyant belirtilmedikçe Mandarin ve Basitleştirilmiş Çince yazı kullanılır.
- Sayılar Çince rakamlarla yazılır, Arap rakamı bırakılmaz. Yıllar rakam rakam okunur: `2026` -> `二零二六年`. Büyük sayılar `万` ve `亿` birimleriyle kurulur: `3.5 million` -> `三百五十万`; `0.7` -> `零点七`; `25%` -> `百分之二十五`; `$10` -> `十美元`.
- Tarih: `June 30, 2026` -> `二零二六年六月三十日`.
- Teknik kimlikler: `4K` -> `四K`, `60fps` -> `每秒六十帧`, `GPT-3.5` -> `GPT三点五`.
- Tam genişlikli noktalama (`，`, `。`, `？`, `！`) kullanılır; sözcükler arasına boşluk konmaz.
- Metin Çince karakterlerle yazılır; Japonca kana kullanılmaz; yalnız kaynak yazımıyla korunan marka ve ürün adları Latin harfli kalabilir.

## sayi_tarih_ornegi
- Geçerli örnek: `一九九九年发生了一场大地震。二零零一年，互联网的使用迅速增长。今天，在二零二六年，我们更好地理解了这些事件。`
- Yasak örnek: `1999年发生了一场大地震。2001年，互联网的使用迅速增长。今天，在2026年，我们更好地理解了这些事件。`
