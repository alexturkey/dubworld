<!--
Genel dil eki: Turkce disindaki her hedef dil icin istemin sonuna eklenir ("## genel"), ayrica istem sablonlarindaki
"<!- - dil:tr ek=ANAHTAR - ->" bloklarinin dilden bagimsiz karsiligini verir (dile ozel dosyada ayni baslik varsa o kullanilir).
Bu giris bolumu (ilk "## " basligina kadar) modele gonderilmez. Bicim ve test: docs/adr/0014-language-independent-translation-prompts.md.
Yer tutucular: {target_lang_name}, {target_lang_name+de}, {target_lang_name_en}, {target_lang_code}.
Bu ekteki kurallar genel dublaj ve TTS ilkeleridir; dile ozel kesin bilgi buraya degil <kod>.md dosyasina yazilir.
-->

## genel
HEDEF DİL EKİ ({target_lang_name} / {target_lang_name_en}, `target_lang={target_lang_code}`):
- Bu işin hedef dili {target_lang_name}: bütün aday metinleri ve çeviri metni yalnız {target_lang_name} yazılır. Talimatların Türkçe yazılmış olması çıktı dilini belirlemez; çıktıya Türkçe kelime, Türkçe ek veya Türkçe örnek cümle girmez.
- Yukarıdaki talimatlarda adı geçen "hedef dil" her yerde {target_lang_name} anlamına gelir.
- Sayılar, tarihler, saatler, yüzdeler, para birimleri, ölçü birimleri ve semboller TTS ile okunacağı için {target_lang_name+nin} doğal sözlü okunuşuyla yazılır; rakam bırakılmaz. Sayı kelimelerinin cinsiyet, hal ve çoğul uyumu {target_lang_name} dilbilgisine uyar.
- Kısaltmalar ve teknik kimlikler (model adı, sürüm, çözünürlük, dosya biçimi) kimliği koruyarak {target_lang_name} konuşmacısının yüksek sesle okuyacağı biçimde yazılır; harfler {target_lang_name} harf okunuşuna göre, rakamlar sözel yazılır.
- {target_lang_name+nin} yerleşik karşılığı olan terimler çevrilir; yerleşik karşılığı olmayan marka, kişi, kurum ve ürün adları kaynak yazımıyla korunur ve `kept_terms` içinde bildirilir.
- Hitap biçimi (resmî/samimi, tekil/çoğul) kaynağın üslubuna göre bir kez seçilir ve bütün videoda tutarlı tutulur.
- Noktalama {target_lang_name} yazım kurallarına uyar; TTS'in okumayacağı dekoratif semboller, emoji, tırnak ve parantez kullanılmaz.
- Metin yazı dili değil, {target_lang_name} konuşma dilidir: kulakta doğal duyulan, insanın ağzından çıkacak cümleler kurulur.

## terimler
- Kaynaktaki genel kavramlar (ör. `mind map`, `slide deck`, `dashboard`, `knowledge vault`) {target_lang_name+nin} yerleşik karşılığıyla çevrilir; seçilen karşılık aynı video içinde değişmez.

## sayi_ornekleri
- `K` kısaltmasını bağlama göre oku: video çözünürlüğünde `4K` ve `8K` harfli kimlik olarak (sayı + harfin {target_lang_name} okunuşu), token veya sayısal ölçekte `8K` ve `120K` "bin" anlamıyla sözel sayı olarak yazılır.
- Teknik biçimleri doğal söyle: `60fps` saniyedeki kare sayısı olarak, `1080p` sayı + harf kimliği olarak, `H.264` harf + nokta + sözel sayı olarak okunur; okunacak `&`, `+` ve `=` sembolleri {target_lang_name} karşılıklarıyla yazılır.

## sayi_sozel
- Tarih, yıl, saat, sayı, yüzde, para, oran, ölçü, sürüm, model, ürün kodu ve teknik değerdeki bütün rakamları {target_lang_name} sözel yazıma çevir. Harfli kimliği koruman gerekiyorsa harfi koru, rakamı yine sözel yaz (`GPT-3.5`: harfler korunur, üç ve beş sözel yazılır).

## sayi_tarih_ornegi

## ondalik
- Nicelik veya matematiksel değerlerde ondalık ayıracı {target_lang_name+nin} ondalık okunuşuyla söylenir (`3.5 million`, `0.7`); yüzde, para birimi ve ölçü birimi {target_lang_name} sözel biçimiyle yazılır (`25%`, `$10`).

## tarih
- Tarihleri {target_lang_name+nin} doğal tarih okunuşuna çevir; gün, ay ve yıl sırası ile ay adları {target_lang_name} kullanımına uyar (`2026-06-30`, `June 30, 2026`).

## sayi_ornek_listesi
- Yıl ve onyıllar, tarih, büyük sayı, ondalık sayı, yüzde, para, hız ve ölçü birimi, saniyedeki kare sayısı, sürüm ve model numarası, çözünürlük ve `&`, `+`, `=` sembolleri {target_lang_name+nin} doğal sözlü biçimiyle yazılır; kaynak örnekleri: `1990s`, `15 March 1990`, `3.5 million`, `0.7`, `25%`, `$10`, `120 km/h`, `60fps`, `24/7`, `GPT-5.5`, `iOS 17.2`, `4K`, `120K`, `H.264`.

## ondalik_ornek
- Örnek: `3.5 kilogram`, `1.25 billion` ondalık miktardır; ayıraç {target_lang_name} ondalık okunuşuyla söylenir.

## surum_ornek
- Örnek kimlikler: `GPT-5.5`, `Opus 4.5`, `iOS 17.2`, `RTX 4090`; harf kısmı korunur, sayı kısmı {target_lang_name} sözel okunuşla yazılır, sürüm ayıracı nokta olarak okunur.

## alfabe
- {target_lang_name} yazımının gerektirdiği bütün harf, aksan ve işaretler eksiksiz kullanılır; aksanı düşürülmüş, Latin harflerine çevrilmiş ya da sadeleştirilmiş yazım kullanılmaz.
