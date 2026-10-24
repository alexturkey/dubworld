# Çeviri aşaması

English: [../engineering/translation.md](../engineering/translation.md)

Çeviri köprülerinin (bridge: dış bir çeviri aracına iş gönderip sonucu geri alan katman) nasıl çalıştığı, sıranın neden
Codex CLI → Claude Code CLI → yerel Opus-MT olduğu ve her sağlayıcıdan ne öğrenildiği.
Karar kayıtları: [ADR 0007](kararlar.md#0007),
[ADR 0008](kararlar.md#0008), [ADR 0009](kararlar.md#0009).

Kod: `bolum_40_ceviri/` — `bridge_motor_orkestratoru/` (gruplama, bağlam, paralel işler, onarım, kullanım raporu),
`llm_kopru/` (tek işçiyi paylaşan Codex ve API arka uçları), `claude_code_cli/`, `yerel_ceviri/` (Opus-MT),
`arka_uc_secimi.py` (arka uç seçimi). Ayarlar: `varsayilan.toml` içinde `[ceviri]`.

## 1. Codex CLI (`codex exec`): asıl kaldıraç yalıtım

- **Sorun:** çeviri çağrıları proje kökünde başlıyordu. Codex her çağrıya projenin ajan talimatlarını, araç ve eklenti
  şemalarını yüklüyordu: daha çok token, daha yavaş ve daha değişken çıktı.
- **Kök neden:** çalışma dizini ve etkin araçlar modelin bağlamının parçasıdır. Saf metin işi bir kodlama ortamında
  çalışıyordu. Kullanıcı düzeyindeki talimat dosyasından da şüphelenildi ve içi boşaltıldı.
- **Çözüm:** komutu tek bir işlev kurar:

```
codex exec --json --skip-git-repo-check --disable <19 features>
  -c model_reasoning_effort="<effort>" --model <model>
  --cd <empty temp dir> --sandbox read-only
  --output-schema <schema> --output-last-message <file> -
```

  - Kapatılan özellikler arasında uygulamalar (apps), tarayıcı kullanımı, bilgisayar kullanımı, kancalar (hooks), görsel
    üretimi, çoklu ajan, eklentiler, kabuk aracı, beceri arama ve diğerleri var.
  - İstem (prompt), iş JSON'u ve tam söylem (discourse: konuşmanın bütün metni) stdin üzerinden gider, asla komut
    satırında değil.
  - Sonuç `--output-last-message` dosyasından okunur; token telemetrisi `turn.completed` olaylarından. Eksik fiyat
    `null` ("doğrulanmadı") olarak kaydedilir, asla 0 olarak değil.
  - Oturum kimliği stderr'den **ve** JSON `thread.started` olayından okunur (yalnız stderr onu kaçırdı); oturum dosyası
    yalnız tek ve tam eşleşmede silinir.
  - İşçi zaman aşımı 900 sn (orkestratörde +60 sn pay). Orkestratör varsayılanları: 10 segmentlik gruplar, 2 segment
    bağlam, 7 paralel iş; geçici grup hatalarında 2, 4, 6, 8, 16, 32 sn geri çekilmeyle (backoff) yeniden deneme.
- **Ölçüldü (aynı 2 segmentlik iş):** girdi tokenları 20.669 (yalıtılmış dizin, araçlar açık) → 16.861 (araçlar kapalı)
  → 17.125 (son sertleştirilmiş istem + şema). Yüzlerce kayıtlı çağrı geride 0 oturum dosyası bıraktı.

### 1.1 Eksik akıl yürütme bayrağı (tek başına en büyük kazanç)

Yapılandırma bir akıl yürütme düzeyi (reasoning effort) tanımlıyordu ama işçi bunu hiç geçirmiyordu.
`-c model_reasoning_effort=...` eklemek çeviri aşamasını aynı girdide **411,1 sn'den 17,5 sn'ye** indirdi (≈ 23,5 kat);
uçtan uca ≈ 8 dk 48 sn → 3 dk 50 sn (ölçüldü). Ders: bir ayarın gerçekten alt sürecin komut satırına ulaştığını doğrula.

### 1.2 Model ve akıl yürütme düzeyi

- Yeniden oynatılan bir istek üzerinde A/B: daha küçük bir "nano" model bu hesap türünde kullanılamıyordu (kesin hata);
  `minimal` düzey kesin hata verir çünkü araçlar minimal düzeyde çalışamaz (asla kullanma); daha hızlı bir kodlama
  modeli ≈ 2 kat hızlıydı ama anlamı ve olumsuzluğu tersine çevirdi ve kodlamayı (encoding) bozdu (dublaj için
  reddedildi).
- Gelecekteki her varsayılan değişikliği için kapı: hesap desteği, `--output-schema` ile kesin hata yok, kimlik/bağlam/aday
  sözleşmesi geçiyor, Türkçe karakterler + anlam + olumsuzluk + korunan terimler sağlam, gerçek bir yeniden oynatmada
  daha hızlı, maliyet kaydedildi.
- Geçerli varsayılanlar: Codex `gpt-5.6-luna`, `medium` düzeyle; Claude `claude-sonnet-5-5`, `medium` ile. Bu iki
  özel seçimi alternatiflere karşı gerekçelendiren **kayıtlı bir A/B yok**; bunları ayarlanabilir sayın.
- **Tam metin kipi 6.000 kaynak kelimenin üzerinde `high` düzeyine geçer.** 10.497 kelimelik bir kaynak `medium` düzeyde
  üç kez `partial` döndü (38.743 girdi tokenı; 9,0k / 14,8k / 11,4k çıktı tokenı; çağrı başına 119–183 sn); aynı girdi
  `high` düzeyde ilk çağrıda başarılı oldu (ölçüldü). Bir `partial` için aynı isteği yeniden denemek hiçbir şeyi
  düzeltmeden token yakar. `medium` düzeyde çalıştığı bilinen aralık: 3.000–5.250 kelime. Güvenli sınır belirlenmedi.
- Bir çalıştırma içinde otomatik model yedeği yok: tek videoda modelleri karıştırmak tonu, JSON disiplinini ve üslubu
  karıştırır.

### 1.3 Windows kurulum ve kimlik doğrulama sorunları

| Belirti | Kök neden | Çözüm |
|---|---|---|
| `codex login status` tamam olduğu halde `401 Unauthorized` | ortamdaki geçersiz bir `OPENAI_API_KEY`, Codex'i API anahtarıyla kimlik doğrulamaya itti | `OPENAI_API_KEY` ve `CODEX_API_KEY` değişkenlerini yalnız **alt sürecin** ortamından kaldır; değer yazmadan `authentication_mode=saved_chatgpt_login` kaydet |
| `windows sandbox: helper_unknown_error: apply deny-read ACLs` | `~/.codex/.sandbox/` altındaki korumalı alan (sandbox) ACL durum dosyası 22 sıfır bayttı | Codex kapalıyken dosyanın adını değiştir; Codex onu yeniden üretir |
| işçi başlamıyordu | genel beceri ağacında UTF-8 olmayan bir dosya | yalnız `auth.json` kopyasını içeren geçici bir `CODEX_HOME` |
| `invalid_json_schema ... schema must have a 'type' key` | `type` içermeyen `const` alanları | her `const` alanına açık bir `type` ver |
| `codex.ps1` engellendi | PowerShell yürütme ilkesi | `codex.cmd` çağır |

Sorun giderme merdiveni: `codex --version` → `codex login status` (ekransız ortamda `--device-auth`) →
`codex exec --skip-git-repo-check "Reply only with OK."` → anahtar değişkenlerinin var olduğunu denetle (değerleri asla
yazdırma) → `codex doctor`. Çıkış kodu 0, çıktı dosyasının yazıldığının kanıtı değildir.

## 2. Claude Code CLI

```
claude --print --output-format json --model <m> --effort <e>
  --system-prompt-file <tmp> --disallowed-tools "*"
  --strict-mcp-config --no-chrome --no-session-persistence
  --permission-mode dontAsk --setting-sources ""
```

- Boş bir geçici dizinde çalışır; iş stdin üzerinden gider; kimlik doğrulama kayıtlı CLI girişidir (`claude auth login`).
  `--bare` kullanılmaz çünkü API anahtarını zorunlu kılar ve kayıtlı girişi devre dışı bırakır.
- `--output-schema` yok: şema sistem istemine eklenir; JSON ayıklanır (önce kod çiti, sonra dengeli süslü parantez
  taraması) ve Codex ile aynı sonuç kapısından geçirilir.
- **Basit bir istekte ölçülen zarf (envelope: modelin her çağrıda yüklediği sabit bağlam) maliyeti:**

| Zarf | Bağlam tokenı | Bildirilen maliyet |
|---|---|---|
| varsayılan | 23.815 | $0.101 |
| yalnız sistem istemi değiştirilmiş | 23.815 | $0.095 |
| kısıtlanmış araçlar | 18.968 | $0.076 |
| **`--disallowed-tools "*"`** | **736** | **$0.003** |

  Yalnız sistem istemini değiştirmek yardımcı olmaz, çünkü araç şemaları yine yüklenir.
- Kip istemini, ASR (otomatik konuşma tanıma) kurallarını ve şemayı **sistem isteminde** tut ki önbelleğe alınsınlar:
  bir çalıştırmanın ikinci çağrısı ilkinin ≈ ¼'üne mal oldu (önbellekten okunan 5.996 token).
- **Yeniden deneme sözleşmesi:** eksik kimlikler ya da boş adaylar → yalnız o kimlikleri isteyen en çok 2 tur; iş
  kimliği uyuşmazlığı → bir tam yeniden çalıştırma; tam metin `partial` → en çok 2 gözden geçirme turu; doğal bloklar
  zincir gözden geçirmesi → 1 tur.

| error_type | yeniden dene | bekleme |
|---|---|---|
| kullanım sınırı | evet | 900 sn |
| aşırı yük / geçici ağ / API hatası | evet | 120 sn |
| zaman aşımı | evet | 300 sn |
| zarf JSON değil | evet | 60 sn |
| sonuç JSON değil | hayır | – |
| kimlik doğrulanmamış | hayır | – |

  HTTP kodları yalnız bir durum bağlamında eşleşir (metindeki çıplak bir "500" hata değildir). Yeniden denemeler aynı
  arka uçta kalır.
- **Gizli yedekler kaldırıldı:** bir Claude seçimi üç yerde (iş kaydı, menü çalışma zamanı, arayüz kilidi) sessizce
  Codex ile üzerine yazılıyordu. Artık geçersiz ya da eksik bir arka uç `BridgeBackendSecimHatasi` fırlatır; tam metin
  kipi tam olarak `{codex, claude_code}` destekler.
- **Kutu kilidi:** API arka uçları, herhangi bir sağlayıcıyı çalıştırabilen tek bir işçinin kopyalarıydı; artık her kutu
  kendi arka uç kimliğini taşır ve herhangi bir çağrıdan önce `bridge_backend_mismatch` ile durur.
- **TTS için okuma kuralı:** aynı tam metin istemiyle Codex 20 çeviride 0 parantez üretti; Claude ise parantez içinde
  İngilizce açıklamalar (gloss) ekledi ve TTS bunları yüksek sesle okuyor. Yalnız Claude'a özel bir kural parantezleri,
  iki dilli açıklamaları ve dipnotları yasaklar. 2.843 karakterlik bir kaynakta ölçüldü: parantez 5 → 0, 60,2 → 51,6 sn.

## 3. İstemler, şemalar ve doğal bloklar sözleşmesi

### 3.1 İstem haritası (kipe göre seçilir)

| Kip | Şema |
|---|---|
| `full_text_translation` | `output_schema_full_text_translation.json` |
| 2 ya da 10 adaylı segment kipleri | `output_schema.json` |
| **`supertonic_natural_blocks_1` (önerilen akış)** | `output_schema_natural_blocks_v2.json` |
| bütün zincir ana metin / adaylar / onarım | `output_schema_supertonic_whole_chain.json` |

- **ASR düzeltmesi** her isteme eklenir (ayrı bir çağrı değildir): kaynak, tanıyıcının tahminidir; yalnız bağlamla
  kanıtlanan, yüksek güvenli yanlış duymalar (adlar, kısaltmalar, sesteş kelimeler, bölünmüş kelimeler) düzeltilebilir;
  tek başına ses benzerliği kanıt değildir; özetleme ya da anlamı segmentler arasında taşıma yok.
- **Tam söylem bağlamı:** sıralı transkriptin tamamı bağlam olarak gönderilir; `main_segment_ids` bu çağrının neyi
  çevirdiğini işaretler.
- **Terimler:** aşırı geniş bir "teknik terimleri kaynak yazımıyla koru" kuralı Türkçe cümlelerin içinde İngilizce
  kelimeler bıraktı. Çözüm: yerleşik Türkçe karşılıklar zorunludur (ör. AI → yapay zeka); çevrilmiş bir terim
  `kept_terms` içinde yer alamaz; bir kod süzgeci hem kaynakta hem adayda bulunmayan korunan terimleri düşürür.

### 3.2 Sayıların ve sembollerin okunuş biçimleri

- **Karar:** okunuş biçimini model yazar; mekanik bir son işleme yok. `K → "ka"` gibi bir kural "8K video"yu (harf olarak
  okunur) "8K tokens"tan (sekiz bin) ayıramaz. Doğrulamadan sonra yeniden yazmak ayrıca altyazı metnini TTS metninden
  ayırır.
- Doğrulanmış tek bir metin hem altyazıyı hem TTS'i besler.
- Doğal bloklar şeması adaylarda Arap rakamlarını yasaklar (`^[^0-9]*[^\s0-9][^0-9]*$`).
- İstemin okunuş biçimi bölümü: bir sayının ya da sembolün rolünü bağlamdan belirle, okunuş biçimini yaz, değeri,
  işareti, birimi ve kimliği denetlemek için içinden geri çevir; ondalık ayırıcı → "virgül", sürüm ayırıcı → "nokta".
  Örnekler yılları, yüzdeleri, para birimlerini, birimleri, sürümleri, çözünürlükleri, kare hızlarını ve kodekleri
  kapsar.

### 3.3 Doğal bloklar (tek doğal aday, anlam kendi segment kimliğine kilitli)

- **Sorun:** segment sınırları cümlelerden değil konuşmadan gelir. Segment segment çeviri altyazı gibi duyulur; serbest
  çevirip yeniden bölmek anlamı komşu kimliğe taşır. İstemde tutulan örnek:
  "I am testing the code to ensure that | the right value is set." şu olmalı:
  "Şundan emin olmak için kodu test ediyorum:" | "doğru değer ayarlanmış." — amaç cümleciğinin öteki kimliğe atladığı
  bir sürüm değil.
- **İstemin gelişimi:** v2 "grubu tek bir Türkçe söz gibi düşün ve cümlecik sınırlarında dağıt" → v3 "niyeti, duyguyu ve
  vurguyu kavra; Türkçe düşün" → **v4 öncelik sırası**: (1) anlam kendi kimliğinde kalır, (2) eksiksiz, hiçbir şey
  eklenmemiş, olgular korunmuş, (3) birleşimi doğal duyulur, (4) sayılar/semboller okunuş biçiminde. Açık bir bağlaçla
  ("that", "because") biten bir kimlik nötr bir köprüyle biter; yalnız noktalamadan oluşan adaylar yasaktır; model
  cevaplamadan önce her kimliği kaynağıyla karşılaştırır.
- **Şema v2:** katı (`additionalProperties: false`); kimlik başına tam olarak bir aday artı `ownership_check`
  {`status`, `source_coverage`, `neighbor_meaning_imported`, `neighbor_meaning_exported`}.
- **Kod kapıları:** beklenen kimlikler eşit; bir aday harf ya da rakam içermeli; felaket düzeyinde kapsama: kaynak
  ≥ 8 kelimeyse ve aday kelime sayısı × 4 < kaynak kelime sayısı ise reddet. Modelin kendi "eksiksiz" iddiasına asla tek
  başına güvenilmez. Gerçek kaynak ve hedefe dayanan bir zincir gözden geçirme yeniden denemesi.
- **Zamanlama burada yalnız öneridir**, asla bir geçerlilik kapısı değildir: doğal Türkçe asla süreyi doldurmak için
  şişirilmez; son zamanlama kararı gerçek sentezlenmiş ses üzerinde verilir (bkz.
  [tts_zamanlama_ve_karisim.md](tts_zamanlama_ve_karisim.md)).
- **Denendi ve kaldırıldı:** her kelimeyi kapsayan birebir kaynak/hedef aralık kanıtı istemek (yerine mantıksal
  bayraklar artı kapsama oranı geldi; nedeni kaydedilmedi). İkinci geçişli bir LLM denetimi (98 segment için 61–97 sn
  ek süre, 9–10 düzeltme, bir çalıştırma kendi doğrulamasında başarısız oldu): hiç bütünleştirilmedi, yaklaşık bir ek
  çeviri geçişine mal olur.
- **Türkçe dışı hedef diller** ([ADR 0014](../adr/0014-language-independent-translation-prompts.md)): istemler ve şemalar
  `llm_kopru/scripts/hedef_dil.py` ile işlenen şablon işaretleri taşır. `tr` için işlenen metin önceki Türkçe istemlerle
  bayt bayt aynıdır (`tests/veri/ceviri_istem_tr_altin.json` içinde 110 altın özet). Diğer hedeflere genel ek
  `dil_ekleri/_genel.md` ve varsa `dil_ekleri/<kod>.md` eklenir (en, de, fr, es, it, pt, ru, ar, ja, zh). Kelime sayısı
  kapıları ve süre tahmini dile göre hız tablosunu kullanır (`tr` kelime başına 0,43 sn, ölçüm; diğerleri tahmin;
  ja/zh/ko/th karakterle sayılır). Yanlış dilde dönen sonuç yeniden denenebilir `translation_result_wrong_language`
  hatası verir (192 doğru metinde 0 yanlış alarm). Gerçek bir LLM ile henüz doğrulanmadı.

## 4. API sağlayıcıları (isteğe bağlı arka uçlar, kendi anahtarınızla)

### Gemini

| Sorun | Kök neden | Çözüm | Ölçülen |
|---|---|---|---|
| "Unterminated string" JSON hataları | `finishReason=MAX_TOKENS` (uygulamanın kendi 8.192 sınırına karşı ≈ 8.180 token) | çıktı sınırı gönderme; bunun yerine grupları boyutlandır | – |
| eksik kimlikler, parçalar önceki kimliklere birleştirildi | tek başına istem de tek başına JSON kipi de kimlikleri zorlamaz; eski yeniden deneme kimlikleri yeniden üretiyordu | katı kip: **kimlik enum'u** içeren JSON şeması, sıcaklık 0.15 (yeniden denemede 0.05), işte zorunlu/salt okunur/yasak kimlik listeleri, kod yinelenenleri/fazlaları reddeder, yeniden deneme yalnız eksik kimlikleri ister | 40/40 kimlik, 0 ihlal |
| katı şema 400 ile reddedildi | desteklenmeyen anahtar kelimeler (`additionalProperties`, `minItems`…), `mimeType` `APPLICATION_JSON` olmalı | en küçük şema | – |
| doğru kimlikler ama anlam kayması | istek zamanlamayı sadakatin üstünde sıralıyordu, bu yüzden kısa segmentler komşu anlamla dolduruldu | istekte `meaning_safety_contract`; uzunluğa göre anlam açısından güvenli en düşük oranlar 0.35/0.40/0.55 | 464/464 segment, 0 ihlal; maliyet $0.443 → $0.294 |
| 503 "high demand" | sağlayıcı kapasitesi | yalnız 503 kapasite mesajları için modele özel yeniden deneme, titreşimli (jitter) 0,5 → 8 sn geri çekilme (≈ 15–20 sn), sonra grubu ertele; 429/401/403/400 hariç | başarı oranı: kayıt yok |
| 32 paralel gruptan biri `Resource deadlock avoided` ile başarısız oldu | istek aralığı kilit dosyasında Windows bayt aralığı kilidi | yeniden denenebilir olarak sınıflandırıldı; yalnız o grup yeniden çalışır | – |

Onarım istemi dersleri: sert "çok uzun" ya da "sıkıştır" talimatları gerçek TTS altında sonuçları kötüleştirdi ve geri
alındı; belirlenimci (deterministic) yinelenen kaldırma TTS ölçümlerini ≈ %18 azalttı; onarım adayları aday sayısıyla
sınırlıdır; döngü turları değil onarımları sayar (bir eksik/fazla bir hatası 5 onarımdan yalnız 4'üne izin vermişti).
Video başına maliyet çıktı klasörünün kullanım raporundan alınır (kanonik kayıt); merkezi bir defter yalnız bir
dizindir.

### Groq, yerel LLM'ler, resmi olmayan Google uç noktası (geçmiş)

- **Groq:** darboğaz para değil, ücretsiz katmanın günlük token sınırıydı; bazı modeller User-Agent başlığı olmadan
  engellendi ya da dakika başına token sınırının üzerindeki istekleri reddetti. Yalnız isteğe bağlı arka uç.
- **llama.cpp ile yerel LLM'ler (4 GB kart, Q4 modeller):** küçük modeller anlam hataları yaptı (süreler, sayılar),
  bağlamı karıştırdı ya da Türkçe kelimeleri bozdu; en iyisi kullanılabilirdi ama 66 sn'lik bir video için ≈ 13 dakika
  sürdü ve sunucu süreci ilk isteğinde sessizce öldü. Dersler: JSON şeması anlamı değil biçimi düzeltir;
  birleştir-sonra-böl anlamı bozar. Taşınmadı; anahtarsız taban olarak yerini Opus-MT aldı.
- **Resmi olmayan Google uç noktası:** hız sınırı yanıtında motor **kaynak metne** geri düştü, böylece İngilizce bir
  metin seslendirildi ve "tamamlandı" olarak teslim edildi. Bu olay sessiz yedek yasağı kuralını doğurdu. Kaldırıldı:
  resmi, belgelenmiş bir yolu yok.

## 5. Yerel Opus-MT

`Helsinki-NLP/opus-mt-tc-big-en-tr` (MarianMT, CC BY 4.0), sabitlenmiş commit + SHA-256, çevrimdışı (`local_files_only`),
toplu iş 16, ışın (beam) 4, `max_new_tokens` 256, GPU ya da CPU. Yalnız İngilizce → Türkçe; diğer dil çiftleri ve tam
metin kipi yapılandırmayla engellenir. Aday yok, sahiplik denetimi yok, ASR düzeltmesi yok, okunuş biçimi kuralları yok,
zamanlama farkındalığı yok. LLM arka uçlarına göre kalite: **kayıt yok**.

**Boş çıktı:** model boş olmayan bir segment için boş çeviri döndürürse motor `YerelCeviriHatasi` fırlatır ve
etkilenen segment numaralarını listeler. Bu durumda kaynak metni döndürmek Google olayındakiyle aynı sessiz yedek kalıbı
olurdu (ADR 0009); bu yüzden yapılmaz.

## 6. Hata sözleşmesi (tüm arka uçlar)

- Sessiz yedek yok; hatalar `raise … from` ile zincirlenir.
- Geçici hatalar grubu yalnız arka ucun sözleşmesinin izin verdiği yerde `deferred` durumuna taşır; yeniden denemeler
  aynı arka uçta kalır.
- Adayı olmayan bir segment `CeviriEksikSegmentError` fırlatır; sayı uyuşmazlığı işi durdurur.
- Tek bir kullanıcı mesajı üreticisi anahtarları ve mutlak yolları maskeler.

## 7. Açık maddeler

1. `high` düzey de `partial` döndürdüğünde parçalı tam metin çevirisi (tasarlandı, uygulanmadı).
2. Opus-MT kalite ölçümü.
3. Gerçek bir videoda Codex ile Claude kalite karşılaştırması; Claude'un segment istemleri için TTS okuma kuralı.
4. Kabul edilen Codex düzeylerinden `minimal`'i kaldırmak.
5. Zamanlamayı bilen bir çeviri belleği (adayları gerçek TTS süreleriyle saklayıp bir güven eşiğinin üzerinde yeniden
   kullanmak) yalnız tasarım aşamasında.
