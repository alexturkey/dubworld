<!--
Russian target appendix. Sources: standard Russian numeral declension and date conventions. Numeral-noun case
agreement is the main risk for spoken text; the rule asks the model to inflect, no closed table is given.
Status: not yet validated in production dubbing.
-->

## genel
Rusça için ek kurallar:
- Sayılar sözel yazılır ve cümledeki hâle göre çekimlenir: `in 1999` -> `в тысяча девятьсот девяносто девятом году`, `2026` -> `две тысячи двадцать шестой год`.
- Sayıdan sonraki isim sayıyla uyumlu hâlde ve sayıda yazılır: `$10` -> `десять долларов`, `25%` -> `двадцать пять процентов`.
- Ondalık değer konuşma diline uygun söylenir: `3.5 million` -> `три с половиной миллиона`; `0.7` -> `ноль целых семь десятых`.
- Tarih: `June 30, 2026` -> `тридцатое июня две тысячи двадцать шестого года`.
- Teknik kimlikler: `4K` -> `четыре К`, `60fps` -> `шестьдесят кадров в секунду`, `GPT-3.5` -> `GPT три точка пять`.
- Hitap: samimi kaynakta `ты`, resmî ya da topluluğa seslenen kaynakta `вы`; seçim bütün videoda değişmez.
- Metin Kiril alfabesiyle yazılır; yalnız kaynak yazımıyla korunan marka ve ürün adları Latin harfli kalabilir.

## sayi_tarih_ornegi
- Geçerli örnek: `В тысяча девятьсот девяносто девятом году произошло сильное землетрясение. В две тысячи первом году интернет начал быстро расти. Сегодня, в две тысячи двадцать шестом году, мы лучше понимаем эти события.`
- Yasak örnek: `В 1999 году произошло сильное землетрясение. В 2001 году интернет начал быстро расти. Сегодня, в 2026 году, мы лучше понимаем эти события.`
