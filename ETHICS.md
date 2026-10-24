# Responsible use / Sorumlu kullanım

This tool transcribes, translates and re-voices video with synthetic speech. Used well, it makes your own content
accessible in another language. Used badly, it can mislead people or infringe their rights. The English text is
binding; the Turkish text is a faithful translation.

## English

**1. Use material you have the right to use.** Process only videos and audio that you own, that are licensed to
you for this purpose, or that you have explicit permission to translate and re-voice. Copyright in the source,
and in the dubbed result as a derivative work, stays with its owners. **You alone are responsible for the content
you process and publish.**

**2. Consent of the people in the material.** Voices and faces are personal data in most jurisdictions (for
example under the EU GDPR and Türkiye's KVKK, Law No. 6698). Get the consent of identifiable people before you
transcribe, dub or publish them, and keep outputs no longer than you need them. The pipeline runs locally; nothing
leaves your machine unless you select an online service (see `THIRD_PARTY.md` §2), in which case that provider's
terms apply.

**3. No impersonation, no voice cloning without consent.** By default the pipeline speaks with built-in synthetic
voices (Supertonic) or with voices designed from a text description (VoxCPM2). Two optional, off-by-default
features can imitate a voice: XTTS-v2 (reference recording) and RVC (voice-conversion model). Any reference
recording or voice model must be **your own voice or a voice whose owner gave explicit, informed consent**; RVC
does not run until you confirm that consent in the settings (`ses.rvc_riza_onayi`). Do not use this project to imitate a real person, to put words in someone's mouth, for fraud, for
disinformation, for harassment, or to deceive anyone about who is speaking. The Supertonic Open RAIL-M license
(Attachment A) and the VoxCPM2 model card forbid these uses too.

**4. Label AI-dubbed content.** Every video produced by the pipeline carries an `AI-dubbed` tag in its metadata.
Do not remove it, and also **tell your audience in a way they can see or hear** (for example "AI-dubbed" in the
title, description or on screen): metadata alone is not a sufficient disclosure. Article 50 of the EU AI Act
(Regulation (EU) 2024/1689), applicable from 2 August 2026, requires deployers to disclose deep-fake audio and video
as artificially generated or manipulated; the Supertonic license also requires disclosing machine-generated content.
Platform rules (for example for synthetic or altered media) may add their own labels.

**5. Downloading from websites (optional `youtube` and `galeri` extras).** URL input uses yt-dlp or gallery-dl only
if you install those extras.
Downloading may be prohibited by a site's terms of service or by your local law even when the tool technically works.
Download only content you own or are clearly permitted to download, and check the site's terms and your local law
first. Tests and examples in this repository never use real third-party URLs or copyrighted media.

**6. Non-commercial engines stay out of commercial work.** The code is Apache-2.0, but some optional engines are
not: **CrisperWhisper 2.0 (Turbo and Medium) and Coqui XTTS-v2 are licensed for non-commercial use only** and are off
by default; you accept their licenses explicitly before use. Do not use non-commercial engines for paid, client or
monetised work. Every engine's commercial status is in `THIRD_PARTY.md`.

**7. Check the result.** Transcription and translation make mistakes. Have a person review the output before you
publish it, and never present it as a verified record (legal, medical, journalistic) without that review.

**8. Disclaimer.** The software is provided "AS IS", without warranty (Apache-2.0 §7–8). The authors and
contributors are not responsible for how you use it or for content you create with it. Comply with the laws of
your jurisdiction and the terms of the services you connect.

Report misuse or a safety issue as described in `SECURITY.md`.

## Türkçe

**1. Hakkınız olan malzemeyi kullanın.** Yalnız sahibi olduğunuz, bu amaçla size lisanslanmış ya da çevirip yeniden
seslendirmek için açık izin aldığınız video ve sesleri işleyin. Kaynağın ve türev eser olan dublajlı sonucun telif
hakkı sahiplerinde kalır. **İşlediğiniz ve yayımladığınız içerikten yalnız siz sorumlusunuz.**

**2. Malzemedeki kişilerin rızası.** Ses ve yüz çoğu hukukta kişisel veridir (ör. AB GDPR ve 6698 sayılı KVKK).
Tanınabilir kişileri yazıya dökmeden, dublajlamadan ya da yayımlamadan önce rızalarını alın; çıktıları gerektiğinden
uzun saklamayın. Hat yerelde çalışır; bir çevrimiçi hizmet seçmedikçe (`THIRD_PARTY.md` §2) makinenizden hiçbir şey
çıkmaz; seçerseniz o sağlayıcının şartları geçerlidir.

**3. Taklit yok, rızasız ses klonlama yok.** Hat varsayılan olarak hazır sentetik seslerle (Supertonic) ya da metin
tarifinden tasarlanmış seslerle (VoxCPM2) konuşur. İki isteğe bağlı, varsayılan kapalı özellik bir sesi taklit
edebilir: XTTS-v2 (referans kayıt) ve RVC (ses dönüştürme modeli). Her referans kayıt ya da ses modeli **kendi
sesiniz ya da sahibinin açık ve bilgilendirilmiş rıza verdiği bir ses** olmalıdır; RVC bu rızayı ayarlarda
onaylamadan (`ses.rvc_riza_onayi`) çalışmaz. Bu projeyi gerçek bir kişiyi taklit
etmek, birinin ağzına söz koymak, dolandırıcılık, dezenformasyon, taciz ya da kimin konuştuğu konusunda kimseyi
yanıltmak için kullanmayın. Supertonic Open RAIL-M lisansı (Ek A) ve VoxCPM2 model kartı da bu kullanımları yasaklar.

**4. Yapay zekâ dublajını etiketleyin.** Hattın ürettiği her videonun meta verisinde `AI-dubbed` etiketi vardır.
Bunu silmeyin; ayrıca **izleyicinize görebileceği ya da duyabileceği biçimde söyleyin** (ör. başlıkta, açıklamada
ya da ekranda "Yapay zekâ ile dublajlanmıştır"): yalnız meta veri yeterli bir açıklama değildir. AB Yapay Zekâ
Tüzüğü (2024/1689) 50. madde, 2 Ağustos 2026'dan itibaren derin sahte (deep fake) ses ve videonun yapay olarak
üretildiğinin ya da değiştirildiğinin açıklanmasını ister; Supertonic lisansı da makine üretimi içeriğin
açıklanmasını şart koşar. Platform kuralları ayrıca kendi etiketlerini isteyebilir.

**5. Sitelerden indirme (isteğe bağlı `youtube` ve `galeri` ekleri).** Bağlantıdan girdi yalnız bu ekleri
kurarsanız yt-dlp ya da gallery-dl ile çalışır. Araç teknik olarak çalışsa bile indirme, sitenin kullanım şartlarınca ya da yerel yasanızca yasak olabilir.
Yalnız sahibi olduğunuz ya da indirme izni açık olan içeriği indirin; önce sitenin şartlarına ve yerel yasanıza bakın.
Bu repodaki testler ve örnekler hiçbir zaman gerçek üçüncü taraf bağlantısı ya da telifli medya kullanmaz.

**6. Ticari olmayan motorlar ticari işe girmez.** Kod Apache-2.0'dır, ama bazı isteğe bağlı motorlar değildir:
**CrisperWhisper 2.0 (Turbo ve Medium) ve Coqui XTTS-v2 yalnız ticari olmayan kullanım için lisanslıdır** ve
varsayılan olarak kapalıdır; kullanmadan önce lisanslarını açıkça kabul edersiniz. Ticari olmayan motorları ücretli, müşteri ya da gelir
getiren işte kullanmayın. Her motorun ticari durumu `THIRD_PARTY.md`'de yazılıdır.

**7. Sonucu kontrol edin.** Yazıya dökme ve çeviri hata yapar. Yayımlamadan önce çıktıyı bir insan gözden
geçirsin; bu kontrol olmadan çıktıyı doğrulanmış kayıt (hukuki, tıbbi, gazetecilik) gibi sunmayın.

**8. Sorumluluk reddi.** Yazılım "OLDUĞU GİBİ", hiçbir garanti olmadan sunulur (Apache-2.0 md. 7-8). Yazarlar ve
katkıcılar yazılımı nasıl kullandığınızdan ya da onunla ürettiğiniz içerikten sorumlu değildir. Bulunduğunuz yerin
yasalarına ve bağladığınız hizmetlerin şartlarına uyun.

Kötüye kullanımı ya da bir güvenlik sorununu `SECURITY.md`'de anlatıldığı gibi bildirin.
