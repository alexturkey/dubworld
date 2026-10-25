# Interface language

[Türkçe](#türkçe) · Code: `src/dublaj_hatti/arayuz_dili.py`, texts: `src/dublaj_hatti/arayuz_dilleri/<code>.json`.

The interface (`dubla-gui` opens it in its own window, `dubla-web` in the browser) is in English and Turkish. Pick the language at the top right. The choice
changes every screen text, the setting descriptions, stage and status names, and the target language names
("German (Deutsch)", "Dub into German"). The job log, deep error messages and the command line stay in Turkish for
now.

## How the language is chosen

| Where | Order |
|---|---|
| Interface | the choice made on the page (kept in that window or browser) > the setting `genel.arayuz_dili` (`auto`, `tr`, `en`) > the browser's languages > the computer's language > English |

A missing text falls back to English, then Turkish, then the key itself, so a half-finished language file never
shows an empty button. Switching the language changes the page in place: the chosen video, your Settings changes
and a running job stay as they are.

## Adding a language

1. Copy `en.json` to `<code>.json` (ISO 639-1, for example `de.json`).
2. Set `_ad` to the language's own name and `_yon` to `ltr` or `rtl`.
3. Translate every value. Write each text the way a native speaker would say it, for someone who has never used the
   app; keep `{placeholders}` as they are. Templates are whole sentences: do not glue words together.
4. `ayar.*` keys describe the settings; a missing one falls back to English.
5. Run `python -m pytest tests/test_arayuz_dili.py`: the tests check the new file on their own (same keys and
   placeholders as Turkish, every key used in the code exists).

No code change is needed: the language list and the `genel.arayuz_dili` choices come from the files.

## Türkçe

Arayüz (`dubla-gui` kendi penceresinde, `dubla-web` tarayıcıda açar) İngilizce ve Türkçedir. Dil sağ üstten seçilir. Seçim ekrandaki bütün yazıları,
ayar açıklamalarını, aşama ve durum adlarını ve hedef dil adlarını ("Almanca (Deutsch)", "Almanca dublajla")
değiştirir. İş günlüğü, derin hata iletileri ve komut satırı şimdilik Türkçe kalır.

### Dil nasıl seçilir

| Nerede | Sıra |
|---|---|
| Arayüz | sayfada yapılan seçim (o pencerede ya da tarayıcıda saklanır) > `genel.arayuz_dili` ayarı (`auto`, `tr`, `en`) > tarayıcının dilleri > bilgisayarın dili > İngilizce |

Eksik bir yazı önce İngilizceye, sonra Türkçeye, en son anahtarın kendisine düşer; yarım kalmış bir dil dosyası boş
düğme göstermez. Dil değişince sayfa yerinde değişir: seçilen video, Ayarlar'daki değişiklikler ve süren iş
olduğu gibi kalır.

### Dil ekleme

1. `en.json` dosyasını `<kod>.json` olarak kopyalayın (ISO 639-1, örneğin `de.json`).
2. `_ad` alanına dilin kendi adını, `_yon` alanına `ltr` ya da `rtl` yazın.
3. Her değeri çevirin. Her yazıyı o dilin konuşucusu nasıl söylerse öyle, uygulamayı hiç kullanmamış biri için
   yazın; `{yer_tutucular}` olduğu gibi kalır. Kalıplar tam cümledir: kelimeleri birbirine yapıştırmayın.
4. `ayar.*` anahtarları ayarları açıklar; eksik olan İngilizceye düşer.
5. `python -m pytest tests/test_arayuz_dili.py` çalıştırın: testler yeni dosyayı kendiliğinden denetler (Türkçeyle
   aynı anahtarlar ve yer tutucular, koddaki her anahtar var).

Kod değişikliği gerekmez: dil listesi ve `genel.arayuz_dili` seçenekleri dosyalardan gelir.
