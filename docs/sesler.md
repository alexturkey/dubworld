# Voices

[Türkçe](#türkçe) · Code: `src/dublaj_hatti/kayit.py` (`SUPERTONIC_SESLER`, `VOXCPM2_HAZIR_SESLER`). Languages per
engine: [diller.md](diller.md).

Only synthetic voices ship with this project. No voice imitates a real person. A reference voice (XTTS) or a
conversion model (RVC) must be your own voice or used with the owner's explicit consent ([ETHICS.md](../ETHICS.md)).

## Supertonic 3 (default)

Ten built-in voice styles from the official model (`voice_styles/*.json`, pinned in `scripts/modeller.json`). The
model publishes no per-voice description, only gender. Each voice has a fixed speech-rate factor tuned for timing
(measured, docs/engineering/tts_timing_and_mix.md).

| Voice | Gender | Rate factor |
|---|---|---|
| `F1` | female | 1.30 |
| `F2` | female | 1.15 |
| `F3` | female | 1.30 |
| `F4` | female | 1.00 |
| `F5` | female | 1.15 |
| `M1` | male | 1.15 |
| `M2` | male | 1.00 |
| `M3` | male | 1.00 |
| `M4` | male | 1.15 |
| `M5` | male | 1.25 |

Settings: `ses.supertonic_ses` (single voice), `ses.konusmaci_cinsiyetine_gore_ses` (speaker separation + gender →
female F1..F5 / male M1..M5 in order of speaking time), `ses.cinsiyet_kipi = "segment"` with `ses.kadin_ses` /
`ses.erkek_ses` (gender per sentence, no speaker separation).

## VoxCPM2 (NVIDIA GPU)

Ready voices from the sister voice-design repository (`hazir_sesler/` at the pinned commit). Use them as
`ses.voxcpm2_ses = "hazir/<id>"`; your own designed voices as `"<name>/<variant>"` or a voice folder path.

| Voice | Language | Description |
|---|---|---|
| `hazir/haber_spikeri` (default) | tr | elderly male news anchor, deep, slightly husky, authoritative |
| `hazir/cekici_spiker` | tr | charismatic female news anchor, full velvety voice, expressive |
| `hazir/belgesel_hanim` | tr | mature female documentary narrator, deep warm alto |
| `hazir/gizemli_bilge` | tr | mature male narrator, deep and powerful, mysterious |
| `hazir/tok_anlatici` | tr | very deep, dense male narrator, heavy and commanding |
| `hazir/yasli_bilge` | tr | old wise man, deep and booming, slow and mysterious |
| `hazir/masal_cadisi` | tr | elderly female fairy-tale narrator, low, slightly nasal, sly |
| `hazir/anlatici_en` | en | native male documentary narrator, mature, deep, calm and warm |
| `hazir/anlatici_fr` | fr | same narrator style, native French |
| `hazir/anlatici_de` | de | same narrator style, native German |
| `hazir/anlatici_es` | es | same narrator style, native Spanish |
| `hazir/anlatici_ru` | ru | same narrator style, native Russian |
| `hazir/anlatici_zh` | zh | same narrator style, native Chinese |
| `hazir/anlatici_ja` | ja | same narrator style, native Japanese |

If the target language is not Turkish and `ses.voxcpm2_ses` is left at the default, that language's ready narrator
is used (`hazir/anlatici_<lang>`); a voice you set yourself is never changed.

### Favorite voices by gender (VoxCPM2)

With `ses.konusmaci_cinsiyetine_gore_ses = true` VoxCPM2 works like Supertonic: speakers are separated, each speaker's
gender is estimated, and the voice comes from your favorite list for that gender. Comma-separated, handed out in
speaker order (the first female speaker gets the first female voice, the second the second; when the list runs out
it starts again):

```toml
[ses]
motor = "voxcpm2"
voxcpm2_kadin_sesleri = "ayse/2, hazir/belgesel_hanim"
voxcpm2_erkek_sesleri = "ali/1, hazir/haber_spikeri, hazir/tok_anlatici"
```

- One voice per gender: write one voice in each list. Several: write several; two speakers never share a voice while
  the list has more.
- Empty lists: the target language's ready voices. Turkish: female `hazir/belgesel_hanim`, `hazir/cekici_spiker`;
  male `hazir/haber_spikeri`, `hazir/tok_anlatici`, `hazir/gizemli_bilge`. Other languages have one male narrator,
  so female speakers also get it and the settings check warns you; design a female voice (the sister repository has
  example prompts, e.g. `en_belgesel_kadin`) and put it in `voxcpm2_kadin_sesleri`.
- One list only: the other gender uses the same list.
- `ses.konusmaci_sesleri` (below) still wins for the speakers you name.
- `ses.cinsiyet_kipi = "segment"`: gender per sentence, the first voice of each list.
- Checks: an unknown `hazir/<id>` is an error; a ready voice of the other gender in a list is a warning.

## Voice library (your own voice)

Open the **Voices** tab, press **Add voice** and pick a recording of 3 to 30 seconds (6 to 15 seconds is best, one
speaker, no music). Give it a name and a category (female, male, child, young, elderly, other), then state whose voice
it is: "this is my own voice" or "the owner explicitly allowed it", and confirm that it does not imitate a real person
without consent ([ETHICS.md](../ETHICS.md)). Without both, **Save** stays off and the line under it says why.

- Optional **transcript of the recording**: if you type exactly what is said in the recording (up to 600 characters),
  VoxCPM2 clones the voice more faithfully. Leave it empty and the voice is cloned from the audio alone.
- Each voice has its own fixed seed, so the same voice sounds the same in every dubbing.
- Use it: press **Use in dubbing** on the card (or pick it under "3. Voice" on the Dub card). The setting is
  `ses.voxcpm2_ses = "kitaplik/<id>"`; it is accepted wherever a VoxCPM2 voice is (`ses.kadin_ses`, `ses.erkek_ses`,
  `ses.konusmaci_sesleri.<speaker>`). A chosen library voice wins over the automatic gender pools.
- Rename, change the category, play, or delete (one confirmation) from the card. Everything is stored on this computer
  under `ayarlar/ses_kitapligi/` (git-ignored; change it with `DUBLAJ_SES_KITAPLIGI`); nothing is uploaded.
- Engine: VoxCPM2 (Apache-2.0, NVIDIA GPU). If you have XTTS installed, a card also offers "Use with XTTS
  (non-commercial licence)", which needs the existing licence acceptance below.

## XTTS v2 (optional, non-commercial weights)

No bundled voice: `ses.xtts_referans_ses` is a 6–15 s recording of **your own voice or a consented voice**. Weights
are under the Coqui Public Model License (non-commercial); accept it once with `ses.xtts_lisans_onayi = true` or
`python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay --kabul`.

## Voice per speaker

`ses.konusmaci_sesleri` maps speaker ids (from `speaker_voice_map.json` in the job folder) to voices and overrides the
automatic choice:

- settings file: `[ses.konusmaci_sesleri]` table, `SPEAKER_00 = "M2"`;
- command line: `--ayar ses.konusmaci_sesleri.SPEAKER_00=M2` or `--ayar "ses.konusmaci_sesleri=SPEAKER_00:M2, SPEAKER_01:F1"`;
- desktop / web *Advanced* tab: the `ses.konusmaci_sesleri` text box (`SPEAKER_00:M2, SPEAKER_01:F1`), with the voices
  of the selected engine listed next to it.

Supertonic accepts F1..F5 / M1..M5 (anything else is a settings error); VoxCPM2 accepts `hazir/<id>` or your own voice;
XTTS ignores the map (one reference voice).

---

## Türkçe

Kod: `src/dublaj_hatti/kayit.py` (`SUPERTONIC_SESLER`, `VOXCPM2_HAZIR_SESLER`). Motor başına diller:
[diller.md](diller.md).

Projeyle yalnız sentetik sesler gelir. Hiçbir ses gerçek bir kişiyi taklit etmez. Referans ses (XTTS) ya da dönüştürme
modeli (RVC) yalnız sizin kendi sesiniz olmalı ya da sahibinin açık izniyle kullanılmalıdır ([ETHICS.md](../ETHICS.md)).

### Supertonic 3 (varsayılan)

Resmî modelden on yerleşik ses biçemi (`voice_styles/*.json`, `scripts/modeller.json` içinde sabitlenmiş). Model ses
başına açıklama yayımlamaz, yalnız cinsiyet. Her sesin zamanlama için ayarlanmış sabit bir konuşma hızı çarpanı vardır
(ölçüldü, docs/engineering/tts_timing_and_mix.md).

| Ses | Cinsiyet | Hız çarpanı |
|---|---|---|
| `F1` | kadın | 1.30 |
| `F2` | kadın | 1.15 |
| `F3` | kadın | 1.30 |
| `F4` | kadın | 1.00 |
| `F5` | kadın | 1.15 |
| `M1` | erkek | 1.15 |
| `M2` | erkek | 1.00 |
| `M3` | erkek | 1.00 |
| `M4` | erkek | 1.15 |
| `M5` | erkek | 1.25 |

Ayarlar: `ses.supertonic_ses` (tek ses), `ses.konusmaci_cinsiyetine_gore_ses` (konuşmacı ayrımı + cinsiyet →
konuşma süresi sırasıyla kadın F1..F5 / erkek M1..M5), `ses.cinsiyet_kipi = "segment"` ile `ses.kadin_ses` /
`ses.erkek_ses` (cümle başına cinsiyet, konuşmacı ayrımı yok).

### VoxCPM2 (NVIDIA GPU)

Kardeş ses tasarımı reposundan hazır sesler (sabitlenmiş commit'teki `hazir_sesler/`). `ses.voxcpm2_ses = "hazir/<id>"`
olarak kullanın; kendi tasarladığınız sesleri `"<name>/<variant>"` ya da bir ses klasörü yolu olarak verin.

| Ses | Dil | Açıklama |
|---|---|---|
| `hazir/haber_spikeri` (varsayılan) | tr | yaşlı erkek haber spikeri, derin, hafif boğuk, otoriter |
| `hazir/cekici_spiker` | tr | karizmatik kadın haber spikeri, dolgun kadife ses, etkileyici |
| `hazir/belgesel_hanim` | tr | olgun kadın belgesel anlatıcısı, derin sıcak alto |
| `hazir/gizemli_bilge` | tr | olgun erkek anlatıcı, derin ve güçlü, gizemli |
| `hazir/tok_anlatici` | tr | çok derin, yoğun erkek anlatıcı, ağır ve buyurgan |
| `hazir/yasli_bilge` | tr | yaşlı bilge adam, derin ve gür, yavaş ve gizemli |
| `hazir/masal_cadisi` | tr | yaşlı kadın masal anlatıcısı, alçak, hafif genizden, kurnaz |
| `hazir/anlatici_en` | en | anadili İngilizce erkek belgesel anlatıcısı, olgun, derin, sakin ve sıcak |
| `hazir/anlatici_fr` | fr | aynı anlatıcı biçemi, anadili Fransızca |
| `hazir/anlatici_de` | de | aynı anlatıcı biçemi, anadili Almanca |
| `hazir/anlatici_es` | es | aynı anlatıcı biçemi, anadili İspanyolca |
| `hazir/anlatici_ru` | ru | aynı anlatıcı biçemi, anadili Rusça |
| `hazir/anlatici_zh` | zh | aynı anlatıcı biçemi, anadili Çince |
| `hazir/anlatici_ja` | ja | aynı anlatıcı biçemi, anadili Japonca |

Toplam 14 hazır ses: 7 Türkçe, 7 dilde birer anlatıcı.

Hedef dil Türkçe değilse ve `ses.voxcpm2_ses` varsayılanda bırakıldıysa o dilin hazır anlatıcısı kullanılır
(`hazir/anlatici_<dil>`); sizin yazdığınız ses hiç değiştirilmez.

#### Cinsiyete göre favori sesler (VoxCPM2)

`ses.konusmaci_cinsiyetine_gore_ses = true` iken VoxCPM2 Supertonic gibi çalışır: konuşmacılar ayrılır, her konuşmacının
cinsiyeti tahmin edilir, ses o cinsiyetin favori listesinden gelir. Liste virgüllüdür, konuşmacı sırasıyla dağıtılır
(1. kadın konuşmacı listenin 1. sesini, 2. kadın 2. sesini alır; liste biterse başa döner):

```toml
[ses]
motor = "voxcpm2"
voxcpm2_kadin_sesleri = "ayse/2, hazir/belgesel_hanim"
voxcpm2_erkek_sesleri = "ali/1, hazir/haber_spikeri, hazir/tok_anlatici"
```

- Her cinsiyete tek ses: listeye tek ses yazın. Birden çok: birden çok yazın; listede ses varken iki konuşmacı aynı
  sesi almaz.
- Liste boşsa hedef dilin hazır sesleri: Türkçe kadın `hazir/belgesel_hanim`, `hazir/cekici_spiker`; erkek
  `hazir/haber_spikeri`, `hazir/tok_anlatici`, `hazir/gizemli_bilge`. Öbür dillerde tek erkek anlatıcı var; kadın
  konuşmacılar da onu alır ve ayar denetimi uyarır. Bir kadın sesi tasarlayın (kardeş repoda örnek tarifler var, ör.
  `en_belgesel_kadin`) ve `voxcpm2_kadin_sesleri` listesine yazın.
- Yalnız bir liste doluysa öbür cinsiyet de o listeyi kullanır.
- `ses.konusmaci_sesleri` (aşağıda) adını verdiğiniz konuşmacılarda yine önce gelir.
- `ses.cinsiyet_kipi = "segment"`: cümle başına cinsiyet, her listenin ilk sesi.
- Denetim: bilinmeyen `hazir/<id>` hatadır; listede öbür cinsiyetin hazır sesi uyarıdır.

### Ses kitaplığı (kendi sesin)

**Sesler** sekmesini aç, **Ses ekle**'ye bas ve 3 ile 30 saniyelik bir kayıt seç (en iyisi 6 ile 15 saniye, tek
konuşmacı, müziksiz). Bir ad ve kategori ver (kadın, erkek, çocuk, genç, yaşlı, diğer), sonra sesin kime ait olduğunu
söyle: "bu benim sesim" ya da "sahibi açıkça izin verdi"; ayrıca gerçek bir kişiyi izni olmadan taklit etmediğini onayla
([ETHICS.md](../ETHICS.md)). İkisi olmadan **Kaydet** kapalı kalır ve altındaki satır nedenini yazar.

- İsteğe bağlı **kaydın metni**: kayıtta ne söylendiyse aynen yazarsan (en çok 600 karakter) VoxCPM2 sesi daha benzer
  klonlar. Boş bırakırsan ses yalnız ses kaydından klonlanır.
- Her sesin kendi sabit tohumu vardır; aynı ses her dublajda aynı duyulur.
- Kullanmak: kartta **Dublajda kullan**'a bas (ya da Dublaj kartında "3. Ses"ten seç). Ayar
  `ses.voxcpm2_ses = "kitaplik/<kimlik>"`; VoxCPM2 sesinin kabul edildiği her yerde geçerlidir (`ses.kadin_ses`,
  `ses.erkek_ses`, `ses.konusmaci_sesleri.<konuşmacı>`). Seçilen kitaplık sesi otomatik cinsiyet havuzlarının önüne geçer.
- Karttan adı değiştir, kategoriyi değiştir, dinle ya da sil (tek onay). Her şey bu bilgisayarda
  `ayarlar/ses_kitapligi/` altında durur (git dışı; `DUBLAJ_SES_KITAPLIGI` ile değişir); hiçbir şey yüklenmez.
- Motor: VoxCPM2 (Apache-2.0, NVIDIA GPU). XTTS kuruluysa kartta ayrıca "XTTS ile kullan (ticari olmayan lisans)"
  görünür; aşağıdaki mevcut lisans onayını ister.

### XTTS v2 (isteğe bağlı, ticari olmayan ağırlıklar)

Hazır ses yok: `ses.xtts_referans_ses`, **sizin kendi sesinizin ya da izin verilmiş bir sesin** 6–15 s'lik kaydıdır.
Ağırlıklar Coqui Public Model License (ticari olmayan) altındadır; bir kez `ses.xtts_lisans_onayi = true` ya da
`python -m dublaj_hatti.bolum_50_seslendirme.xtts_tts onay --kabul` ile kabul edin.

### Konuşmacı başına ses

`ses.konusmaci_sesleri` konuşmacı kimliklerini (iş klasöründeki `speaker_voice_map.json` içinden) seslere eşler ve
otomatik seçimi ezer:

- ayar dosyası: `[ses.konusmaci_sesleri]` tablosu, `SPEAKER_00 = "M2"`;
- komut satırı: `--ayar ses.konusmaci_sesleri.SPEAKER_00=M2` ya da `--ayar "ses.konusmaci_sesleri=SPEAKER_00:M2, SPEAKER_01:F1"`;
- masaüstü / web *Gelişmiş* sekmesi: `ses.konusmaci_sesleri` metin kutusu (`SPEAKER_00:M2, SPEAKER_01:F1`); yanında
  seçili motorun sesleri listelenir.

Supertonic F1..F5 / M1..M5 kabul eder (başka değer ayar hatasıdır); VoxCPM2 `hazir/<id>` ya da kendi sesinizi kabul
eder; XTTS eşlemeyi yok sayar (tek referans ses).
