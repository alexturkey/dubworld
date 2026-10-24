# Per-segment gender mode (`segment_cinsiyet_kipi`)

[Türkçe](#türkçe) · registry row: `src/dublaj_hatti/kayit.py` (`dubla kontrol` shows whether it is installed)

**What it does:** Instead of one voice per speaker, predicts the speaker gender of **every sentence** separately and
gives that sentence the female/male voice you chose in Supertonic. Sentences shorter than 0.30 s take the voice of the
nearest reliable neighbour. Speaker separation (3D-Speaker) does not run; it is more flexible in multi-speaker but
mixed scenes, and the same person's voice can change from sentence to sentence (in speaker mode it does not).

| | |
|---|---|
| License | Apache-2.0 (code and weights: alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech @7a28165f; training data LibriSpeech CC BY 4.0) |
| Install | default models (`scripts/kur.ps1 -Adim modeller`) |
| Hardware | GPU or CPU; model 1.26 GB, ~3 GB RAM on the CPU (estimate) |
| Default | off (the recommended flow is in speaker mode) |

**Setting:** `ses.konusmaci_cinsiyetine_gore_ses = true` and `DubConfig.cinsiyet_kipi = "segment"`,
`supertonic_kadin_ses` (F1-F5), `supertonic_erkek_ses` (M1-M5). The settings-file keys (`ses.cinsiyet_kipi`,
`ses.kadin_ses`, `ses.erkek_ses`) are read from here once they are added to the settings layer. Report: a gender
routing report in the job folder (gender, confidence and decision source per sentence).

**Common errors**
- Only one voice in the output → the models are not installed (warning in the log); `kur.ps1 -Adim modeller`.
- Children's or very high-pitched voices can be misclassified; try speaker mode or a manual speaker map.

## How it works in this pipeline / Neden böyle

- **Principle:** speaker separation does not run; the gender classifier evaluates every sentence separately and gives
  that sentence the selected female or male Supertonic voice. Sentences shorter than 0.30 s take the decision of the
  nearest reliable neighbour.
- **Why this choice:** it is a light path without speaker clustering; it is flexible in mixed scenes where speaker
  separation under-counts. The cost: the same person's voice can change from sentence to sentence, and a sentence
  spoken by two people gets one gender. There is no confidence threshold; no Turkish accuracy measurement is recorded.
- **How it fits:** the gender worker processes all sentences at once in a single subprocess and exits; the result goes
  to the Supertonic voice selection, and timing and translation do not change.
- Details: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2–§3 · [cinsiyet_siniflandirici](cinsiyet_siniflandirici.md)
- Place in the end-to-end flow: [pipeline-flow.md, stage table](../engineering/pipeline-flow.md#3-stage-table-segment-sync-the-default)

## Türkçe

**Segment bazlı cinsiyet kipi (`segment_cinsiyet_kipi`)**

**Ne yapar:** Konuşmacı başına ses yerine **her cümlenin** konuşmacı cinsiyetini ayrı tahmin eder ve Supertonic'te
seçtiğiniz kadın/erkek sesini o cümleye verir. 0,30 sn'den kısa cümleler en yakın güvenilir komşunun sesini alır.
Konuşmacı ayrımı (3D-Speaker) çalışmaz; çok konuşmacılı ama karışık sahnelerde daha esnektir, aynı kişinin sesi
cümleden cümleye değişebilir (konuşmacı kipinde değişmez).

| | |
|---|---|
| Lisans | Apache-2.0 (kod ve ağırlık: alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech @7a28165f; eğitim verisi LibriSpeech CC BY 4.0) |
| Kurulum | varsayılan modeller (`scripts/kur.ps1 -Adim modeller`) |
| Donanım | GPU ya da işlemci; model 1,26 GB, işlemcide ~3 GB RAM (tahmini) |
| Varsayılan | kapalı (Önerilen akış konuşmacı kipindedir) |

**Ayar:** `ses.konusmaci_cinsiyetine_gore_ses = true` ve `DubConfig.cinsiyet_kipi = "segment"`,
`supertonic_kadin_ses` (F1-F5), `supertonic_erkek_ses` (M1-M5). Ayar dosyası anahtarları (`ses.cinsiyet_kipi`,
`ses.kadin_ses`, `ses.erkek_ses`) ayar katmanına eklenince buradan okunur. Rapor: iş klasöründe cinsiyet
yönlendirme raporu (cümle başına cinsiyet, güven, karar kaynağı).

**Sık hata**
- Tek ses çıktı → modeller kurulu değil (uyarı günlükte); `kur.ps1 -Adim modeller`.
- Çocuk/çok tiz sesler yanlış sınıflanabilir; konuşmacı kipini ya da elle konuşmacı haritasını deneyin.

### Bu hatta nasıl çalışır / Neden böyle

- **İlke:** konuşmacı ayrımı çalışmaz; cinsiyet sınıflandırıcı her cümleyi ayrı değerlendirir ve seçilen kadın ya da
  erkek Supertonic sesini o cümleye verir. 0,30 sn'den kısa cümleler en yakın güvenilir komşunun kararını alır.
- **Neden böyle:** konuşmacı kümelemesi olmadan hafif bir yoldur; konuşmacı ayrımının sayıyı eksik bulduğu karışık
  sahnelerde esnektir. Bedeli: aynı kişinin sesi cümleden cümleye değişebilir ve iki kişinin konuştuğu bir cümle tek
  cinsiyet alır. Güven eşiği yoktur; Türkçe doğruluk ölçümü kayıtlı değildir.
- **Diğer parçalarla ahengi:** cinsiyet işçisi tek alt süreçte bütün cümleleri bir kerede işler ve çıkar; sonuç
  Supertonic ses seçimine gider, zamanlama ve çeviri değişmez.
- Ayrıntı: [speakers_and_segments.md](../engineering/speakers_and_segments.md) §2–§3 · [cinsiyet_siniflandirici](cinsiyet_siniflandirici.md)
- Uçtan uca akıştaki yeri: [hat_akisi.md, aşama tablosu](../muhendislik/hat_akisi.md#3-aşama-tablosu-segment-eşleme-varsayılan)
