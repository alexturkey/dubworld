# Başlarken (programlama bilgisi gerekmez)

[English](getting-started.md) · Tam kurulum belgesi: [kurulum.md](kurulum.md)

Bu program bir videoyu alır, içinde söyleneni dinler, çevirir ve videonun yeni bir kopyasını yapar: bu kopyada
çeviriyi bilgisayar sesi okur, altyazı da eklenir. Her şey kendi bilgisayarınızda çalışır; videonuz hiçbir yere
yüklenmez (tek istisna aşağıda, "Başka bir dil seçmek" bölümünde).

## Neye ihtiyacınız var

- **Windows 10 ya da 11** yüklü bir bilgisayar (64 bit). Mac ve Linux henüz denenmedi.
- **Boş disk yeri:** bilgisayarda NVIDIA ekran kartı varsa yaklaşık 22 GB, yoksa yaklaşık 14 GB. NVIDIA kartlı ölçülen bir kurulum yaklaşık 14,6 GB kullanır; Windows Gezgini yaklaşık
  22 GB gösterir, çünkü indirme önbelleği dosyalarının çoğunu programla paylaşır ve Gezgin onları iki kez sayar.
- Yalnız kurulum sırasında **internet**.
- **Ekran kartı** şart değildir. *Ekran kartı* (*GPU* da denir) bilgisayarın görüntüyü çizen parçasıdır; NVIDIA
  kartlar bu programın ağır işini de yapabilir ve onu çok hızlandırır. Kart yoksa bütün işi *işlemci* (*CPU*,
  bilgisayarın ana yongası) yapar, yalnız daha yavaş.
- **Kullanma hakkınız olan** bir video: kendi videonuz ya da sahibinin izin verdiği bir video.

## Kolay kurulum: yapay zekâ asistanınıza kurdurun

*Yapay zekâ asistanı* burada bilgisayarınızda sizin yerinize komut çalıştırabilen bir program demektir: Claude
Code, Codex, Gemini CLI gibi. Asistanı açın ve şu tek cümleyi yapıştırın (adres, bu programı bulduğunuz sayfadır):

```text
https://github.com/alexturkey/DubWorld adresindeki video dublaj programını bu bilgisayara kur. Depodaki AGENTS.md dosyasını adım adım uygula, donanımımı kendin algıla, bana teknik soru sorma. `dubla kontrol` HAZIR deyip örnek dublaj çalışınca programın penceresini benim için aç.
```

Asistan bilgisayarı ölçer ve ekran kartıyla mı işlemciyle mi kurulacağını kendisi seçer. Sonra size bir kez, sade
sözcüklerle **nasıl bir kurulum istediğinizi** sorar: hızlı, bilgisayarınız için önerilen ya da tam; her parçanın
ne yaptığını, ne kadar disk yeri ve zaman istediğini, lisansının neye izin verdiğini söyler. Programın konuştuğu
sesin kullanım şartlarını kabul edip etmediğinizi de sorar. Kısaca şunu söyler: gerçek kişileri taklit etmeyin,
kimseyi kandırmayın, izleyicinize sesin bilgisayar yapımı olduğunu söyleyin. Kabul ediyorsanız "evet" deyin.
Sonra gerekenleri indirir, küçük bir örnek videoyla dener ve program penceresini açar. Program penceresi şimdilik
Türkçedir.

İndirme yaklaşık 13 GB'tır (NVIDIA kartı yoksa 9,5 GB); ölçülen ilk kurulumlar yaklaşık 38 dakika (NVIDIA kartı yokken) ve yaklaşık 44 dakika (kartla; çoğu model
indirmesiydi) sürdü. Hızlı bağlantıda daha kısa sürer.

## Kendiniz kurmak

1. Proje sayfasında yeşil **Code** düğmesine, sonra **Download ZIP**'e tıklayın. ZIP'i kısa ve boşluksuz bir
   klasöre açın, örneğin `C:\dublaj`.
2. O klasörde **`kur.cmd`** dosyasına çift tıklayın. Windows mavi bir "Windows bilgisayarınızı korudu" penceresi
   gösterirse **Ek bilgi**'ye, sonra **Yine de çalıştır**'a tıklayın (yalnız programı resmî sayfasından
   indirdiyseniz).
3. Siyah bir pencere ilerlemeyi gösterir; kapatmayın. **Kurulum bitti** yazınca bir tuşa basın. **KURULUM DURDU /
   INSTALL STOPPED** yazarsa altındaki satırlar ne yapılacağını söyler; çoğu zaman `kur.cmd`'ye yeniden çift
   tıklamak yeter (kaldığı yerden sürer).

## İlk dublajınız

1. Program klasöründe **`arayuz.cmd`** dosyasına çift tıklayın. Program penceresi açılır.
2. İlk sekmede, **Önerilen akış**'ta kalın. **Video seç…** düğmesine tıklayıp videonuzu seçin.
3. **Dublaj dili** listesinden dili seçin. Her dil kendi dilinde yazar (Türkçe, English, Deutsch, Français, 日本語 …);
   siz değiştirmedikçe Türkçe seçilidir. Büyük düğme dilin adını alır: **Türkçe dublajla**, **English dublajla**,
   **Deutsch dublajla** …
4. O düğmeye tıklayın. İlk seferde bir pencere sesin kullanım şartlarını kabul etmenizi ister
   (yukarıya bakın); kabul ediyorsanız **Evet**'e tıklayın.
5. Bekleyin. Alttaki çubuk ne kadar ilerlediğini gösterir. NVIDIA ekran kartı olmayan bilgisayarda daha yavaştır.
6. **Bitti** yazınca izlemek için **Videoyu aç**'a ya da **Çıktı klasörünü aç**'a tıklayın. Sonuçlar program
   klasörünün içindeki `cikti` klasöründe durur.

Pencerede kırmızı **Kurulum tamamlanmamış** satırı görürseniz `kur.cmd`'ye yeniden çift tıklayın, sonra programı
yeniden açın.

## Başka bir dil seçmek

Siz değiştirmedikçe program **Türkçeye** dublaj yapar. Başka bir dili ilk sekmedeki **Dublaj dili** listesinden
seçin; düğmenin adı da değişir (örneğin **Deutsch dublajla**). Bu liste ile **Gelişmiş** sekmesindeki
`genel.hedef_dil` satırı aynı ayardır: birini değiştirince öteki de değişir. Listede yalnız seçili ses motorunun
konuşabildiği diller görünür; *denenmedi* işaretli dil çalışır ama kulakla denetlenmemiştir. Web sayfasında
(`web.cmd`) aynı liste vardır.

Programla gelen çevirmen yalnız **İngilizceden Türkçeye** ve internetsiz çevirir. Başka her dil çifti için çevrimiçi
bir çevirmen gerekir: Codex ya da Claude Code asistanı (biri kurulu ve oturumu açıksa kendiliğinden kullanılır) ya da
bir çeviri hizmetinin anahtarı. Bu durumda videonun kendisi değil, *metni* o hizmete gider. En kolayı asistanınıza
söylemek, örneğin: "dublaj programında Almancaya çeviriyi kur".

## Buradaki kelimeler

| Kelime | Anlamı |
|---|---|
| Dublaj | bir videodaki konuşmayı başka dilde konuşmayla değiştirmek |
| GPU / ekran kartı | bilgisayarın görüntüyü çizen parçası; NVIDIA olanı bu programı hızlandırır |
| CPU / işlemci | bilgisayarın ana yongası; bütün işi yapabilir, yalnız daha yavaş |
| Model | programın öğrendiği büyük dosya; kurulumda bir kez iner |
| Kurulum | programı ve modellerini bilgisayara yerleştirmek (her şey program klasörüne gider) |
| Altyazı | videonun altında görünen yazı |
| `AI-dubbed` etiketi | sonuç dosyasının içinde, sesi bilgisayarın yaptığını söyleyen gizli not; silmeyin |
| Günlük | programın ne yaptığının teknik dökümü; bir sorun olunca asistanınıza göndermek işe yarar |

## Sık sorunlar

| Ne görüyorsunuz | Ne yapmalı | Ya da asistanınıza şunu söyleyin |
|---|---|---|
| Kurulum penceresinde **KURULUM DURDU / INSTALL STOPPED** | `kur.cmd`'ye yeniden çift tıklayın; kaldığı yerden sürer | "Kurulum şu mesajla durdu: … Düzeltir misin?" |
| "running scripts is disabled on this system" | `scripts` klasöründeki dosyaları değil `kur.cmd`'yi kullanın | "AGENTS.md adımlarıyla kur." |
| Disk yerinin yetmediği yazıyor | yer açın (yaklaşık 22 GB, NVIDIA kartı yoksa 14 GB) ya da klasörü başka sürücüye koyun | "Dublaj programını D: sürücüsüne taşı ve kurulumu bitir." |
| Program penceresinde kırmızı **Kurulum tamamlanmamış** satırı | `kur.cmd`'ye yeniden çift tıklayın, sonra pencereyi yeniden açın | "Dublaj programının kurulumunu denetle, eksik ne varsa tamamla." |
| Dublaj çok yavaş | NVIDIA ekran kartı yoksa normaldir; varsa kart kullanılmıyor olabilir (çoğunlukla eski sürücü) | "Dublaj programı ekran kartımı kullanıyor mu, bak." |
| Bir pencere **lisans** onayı istiyor | okuyun; sesin kullanım şartlarıdır. Yalnız kabul ediyorsanız onaylayın | – |
| Çeviri ya da dil hatası | programla gelen çevirmen yalnız İngilizce → Türkçe çevirir; "Başka bir dil seçmek" bölümüne bakın | "Dublaj programında İspanyolcadan Türkçeye çeviriyi kur." |
| **İş başarısız** | **İşler** sekmesini açın; duran iş oradan sürdürülebilir. *Günlüğü göster*'e tıklayıp son satırları kopyalayın | "Dublajım başarısız oldu, günlük şu: … Düzeltir misin?" |
| Programı kaldırmak istiyorsunuz | program klasörünü silin; bilgisayarda başka hiçbir şey değiştirilmedi | – |

## Lütfen sorumlu kullanın

Yalnız sahibi olduğunuz ya da kullanma izniniz olan videoları dublajlayın, gerçek kişilerin sesini taklit
etmeyin. İzleyicilerinize dublajın yapay zekâyla yapıldığını söyleyin. Ayrıntılar [../ETHICS.md](../ETHICS.md)
dosyasında, bilgisayarınızda nelerin kaldığı [../PRIVACY.md](../PRIVACY.md) dosyasında.
