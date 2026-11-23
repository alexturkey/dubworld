# AGENTS_HIZLI.md: quick card for AI coding agents / Yapay zekâ ajanları için hızlı kart

English first, Türkçe below. Full rules and evidence: [`AGENTS.md`](AGENTS.md) (it wins if the two ever differ). Error codes: `docs/hata_imzalari.json`, `docs/troubleshooting.md`.

## EN

### Decision tree (12 steps)
1. Goal: install DubWorld (a video dubbing program) for the user on their own Windows 10/11 PC and make one sample dub. Anything else: tell the user and stop.
2. Defaults are fixed: do not change a model, a pinned hash or a quality setting to make something pass.
3. Dry run first, it writes nothing: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Kuru`. Read every `HATA:` / `UYARI:` line; each carries a code such as `[DW-E-DISK]`.
4. A non-zero exit or any `HATA` in that list: take it to the user with the code and its first step from `docs/hata_imzalari.json`. Do not use a force flag to get past it.
5. Ask the user once (AGENTS.md step 1a): which setup, and whether they accept the licence conditions of what they chose (licence and consent steps belong to the human; never type the acceptance yourself).
6. Install: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` (safe to re-run; verified files are skipped).
7. First success: `.venv\Scripts\dubla.exe kontrol`, then the sample dub of AGENTS.md step 4. A first install takes up to an hour: start it hidden in the background and poll the log; do not block.
8. Exit 0 means the step passed, nothing more: `dubla kontrol` must print `READY` and the sample dub must print a `dubbed_video:` line whose file exists.
9. A failed or not-run step means the result is NOT accepted. Never report success.
10. A line with a code: look it up in `docs/hata_imzalari.json` (or run `scripts\tani.ps1 -Log kur.log`), give the user its first step, quote the code. Same error twice: stop, do not try a third time.
11. Paths and files are only what the user gave you. Never pick a file yourself.
12. Report in the user's language, with the code and the first 20 log lines. No personal paths, user names, e-mail addresses or tokens: write `<ROOT>`.

### Exit code to action
| Script | Exit | Meaning | What you do | Codes |
|---|---|---|---|---|
| `scripts\kur.ps1 -Kuru` | 0 | READY: nothing blocks the install | start the install (step 6) | none |
| `scripts\kur.ps1 -Kuru` | 2 | a licence step needs the human's acceptance (and no environment error) | ask the user; never pass `-TicariOlmayanKabul` yourself | DW-E-LISANS |
| `scripts\kur.ps1 -Kuru` | 3 | environment not ready (one or more `HATA:` lines) | take the lines to the user; do not install | DW-E-DISK, DW-E-ADIM, DW-E-ONCE-TABAN, DW-E-WSL, DW-E-GIT |
| `scripts\kur.ps1` | 0 | `KURULUM_OK` | verify (step 7) | none |
| `scripts\kur.ps1` | 1 | `KURULUM DURDU` | run the same command once more; then `scripts\tani.ps1 -Log kur.log`; stop after the second identical failure | DW-E-SHA, DW-E-PAKET, DW-E-MODEL, DW-E-PYTHON, DW-E-TORCH, DW-E-POLITIKA |
| `scripts\denetim.py` | 0 | all gates passed | nothing | none |
| `scripts\denetim.py` | 1 | at least one gate is red | read the named gate; fix the cause, never switch the gate off | none |
| `scripts\denetim.py` | 3 | input or environment problem | check the repository folder and the gate name | none |
| `scripts\denetim.py` | 6 | a gate did not run (a tool is missing) | install the tool it names; do not read this as green | none |
| `scripts\pr_kapi.py` | 0 | passed or only protected-path notes | a human still reads the diff | none |
| `scripts\pr_kapi.py` | 1 | a red pattern | do not merge; a human reviews with a second key | none |
| `scripts\pr_kapi.py` | 3 | bad input | check the arguments | none |
| `scripts\pr_kapi.py` | 4 | no red, but a content signal | a human must look | none |
| `scripts\pr_kapi.py` | 6 | the gate did not run | not green | none |
| `dubla <video>` | 0 | dub finished | find the `dubbed_video:` line | none |
| `dubla <video>` | 1 | job failed | `.venv\Scripts\dubla.exe sorunlu` shows why | none |
| `dubla <video>` | 2 | licence or setting problem (the message says which) | ask the user; never pass `--lisans-onay` without their yes | DW-E-LISANS-DUBLA |

## TR

### Karar ağacı (12 adım)
1. Amaç: kullanıcının kendi Windows 10/11 bilgisayarına DubWorld'ü (video dublaj programı) kurmak ve bir örnek dublaj yapmak. Başka bir iş: kullanıcıya söyle ve dur.
2. Varsayılanlar sabittir: bir şeyi geçirmek için modeli, sabit hash'i ya da kalite ayarını değiştirme.
3. Önce kuru çalıştır, hiçbir şey yazmaz: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1 -Kuru`. Her `HATA:` / `UYARI:` satırını oku; her biri `[DW-E-DISK]` gibi bir kod taşır.
4. Sıfır olmayan çıkış ya da listede herhangi bir `HATA`: kodu ve `docs/hata_imzalari.json`'daki ilk adımı kullanıcıya götür. Zorlayıcı bayrakla geçme.
5. Kullanıcıya bir kez sor (AGENTS.md adım 1a): hangi kurulum ve seçtiklerinin lisans koşullarını kabul ediyor mu (lisans ve onay adımları insanındır; kabulü asla kendin yazma).
6. Kurulum: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` (tekrar çalıştırmak güvenli; doğrulanmış dosya atlanır).
7. İlk başarı: `.venv\Scripts\dubla.exe kontrol`, sonra AGENTS.md adım 4'teki örnek dublaj. İlk kurulum bir saate kadar sürer: gizli arka planda başlat, günlüğü yoklayarak izle; bekleyerek kilitlenme.
8. Çıkış 0 yalnız adımın geçtiği demektir: `dubla kontrol` `READY` yazmalı, örnek dublaj var olan bir dosyayı gösteren `dubbed_video:` satırı basmalı.
9. Başarısız ya da çalışmayan adım: sonuç KABUL EDİLMEZ. Asla başarı bildirme.
10. Kodlu satır: `docs/hata_imzalari.json`'da ara (ya da `scripts\tani.ps1 -Log kur.log` çalıştır), ilk adımı kullanıcıya ver, kodu yaz. Aynı hata iki kez: dur, üçüncü kez deneme.
11. Yol ve dosya yalnız kullanıcının sana verdiğidir. Kendin dosya seçme.
12. Kullanıcının dilinde, kodla ve günlüğün ilk 20 satırıyla bildir. Kişisel yol, kullanıcı adı, e-posta, token yazma: `<ROOT>` yaz.

### Çıkış kodu -> eylem
| Betik | Çıkış | Anlam | Ne yaparsın | Kodlar |
|---|---|---|---|---|
| `scripts\kur.ps1 -Kuru` | 0 | HAZIR: kurulumu engelleyen bir şey yok | kurulumu başlat (adım 6) | yok |
| `scripts\kur.ps1 -Kuru` | 2 | lisans adımı insanın kabulünü ister (ortam hatası yok) | kullanıcıya sor; `-TicariOlmayanKabul`'u kendin verme | DW-E-LISANS |
| `scripts\kur.ps1 -Kuru` | 3 | ortam hazır değil (bir ya da daha çok `HATA:` satırı) | satırları kullanıcıya götür; kurma | DW-E-DISK, DW-E-ADIM, DW-E-ONCE-TABAN, DW-E-WSL, DW-E-GIT |
| `scripts\kur.ps1` | 0 | `KURULUM_OK` | doğrula (adım 7) | yok |
| `scripts\kur.ps1` | 1 | `KURULUM DURDU` | aynı komutu bir kez daha çalıştır; sonra `scripts\tani.ps1 -Log kur.log`; ikinci aynı başarısızlıkta dur | DW-E-SHA, DW-E-PAKET, DW-E-MODEL, DW-E-PYTHON, DW-E-TORCH, DW-E-POLITIKA |
| `scripts\denetim.py` | 0 | bütün kapılar geçti | bir şey yapma | yok |
| `scripts\denetim.py` | 1 | en az bir kapı kırmızı | adı geçen kapıyı oku; nedeni düzelt, kapıyı asla kapatma | yok |
| `scripts\denetim.py` | 3 | girdi ya da ortam sorunu | depo klasörünü ve kapı adını denetle | yok |
| `scripts\denetim.py` | 6 | bir kapı çalışmadı (araç eksik) | adı geçen aracı kur; bunu yeşil sayma | yok |
| `scripts\pr_kapi.py` | 0 | geçti ya da yalnız korumalı yol notu | diff'i yine bir insan okur | yok |
| `scripts\pr_kapi.py` | 1 | kırmızı desen | birleştirme; insan ikinci anahtarla inceler | yok |
| `scripts\pr_kapi.py` | 3 | hatalı girdi | argümanları denetle | yok |
| `scripts\pr_kapi.py` | 4 | kırmızı yok ama içerik sinyali var | bir insan bakmalı | yok |
| `scripts\pr_kapi.py` | 6 | kapı çalışmadı | yeşil değildir | yok |
| `dubla <video>` | 0 | dublaj bitti | `dubbed_video:` satırını bul | yok |
| `dubla <video>` | 1 | iş başarısız | `.venv\Scripts\dubla.exe sorunlu` nedenini gösterir | yok |
| `dubla <video>` | 2 | lisans ya da ayar sorunu (mesaj hangisi olduğunu söyler) | kullanıcıya sor; evet'i olmadan `--lisans-onay` verme | DW-E-LISANS-DUBLA |
