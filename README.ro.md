# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · Română · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld vă dublează videoclipurile în altă limbă direct pe calculatorul dumneavoastră, fără să le încarce pe vreun serviciu online: transformă vorbirea în text împreună cu momentul fiecărui cuvânt, o traduce și o citește cu o voce artificială (AI) care ține pasul cu imaginea originală (vorbirea e accelerată cel mult de 1,25 ori, restul diferenței e preluat de o ușoară schimbare a ritmului video), adaugă subtitrări și creează un videoclip nou. Limba implicită este turca; româna și celelalte limbi depind de motorul de voce ales ([docs/diller.md](docs/diller.md)).

## Lăsați asistentul AI să-l instaleze

Nu trebuie să știți programare. Deschideți un asistent AI care poate rula comenzi pe calculatorul dumneavoastră (Claude Code, Codex,
Gemini CLI sau ceva asemănător) și lipiți această singură propoziție:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Asistentul vă verifică calculatorul (placa video, procesorul, memoria, discul) și vă întreabă o singură dată, pe înțelesul
tuturor, ce fel de instalare doriți: rapidă, recomandată pentru calculatorul dumneavoastră sau completă. Explică fiecare
componentă (ce face, cât spațiu ocupă, cât durează, ce licență are) și, începând cu vocea implicită, vă întreabă dacă acceptați
condițiile de utilizare ale componentelor alese. Apoi instalează, face o dublare de probă și deschide fereastra programului.
Primii pași și problemele frecvente, explicate simplu (în engleză): **[docs/getting-started.md](docs/getting-started.md)**.

**Licențele pe scurt:** codul Apache-2.0. Modele implicite: vocea Supertonic 3 sub OpenRAIL-M (restricții de utilizare, acceptate o dată); Opus-MT și modelul turcesc de timp al cuvintelor sub CC BY 4.0 (atribuire obligatorie, NOTICE); build-ul FFmpeg GPL-3.0 (program separat). Doar pentru uz necomercial și dezactivate implicit: CrisperWhisper 2.0, XTTS-v2 și modelele WhisperX de timp al cuvintelor pentru fr / de / es / it. Depozitul nu conține nicio pondere de model ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Instalare rapidă

Windows 10/11 x64; nu e nevoie de Python, CUDA sau ffmpeg instalate dinainte. Faceți dublu clic pe **`kur.cmd`** (sau rulați
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); profilul GPU sau CPU se alege singur
(`-Cpu` forțează CPU). Apoi dublu clic pe `arayuz.cmd` ca să deschideți aplicația.
Totul rămâne în folderul depozitului (`.venv`, `runtime_assets/`); fiecare descărcare are versiunea fixată și
e verificată cu sha256. Spațiu liber ca să începeți: 22 GB cu profilul GPU, 14 GB doar cu CPU; ocupare măsurată după instalare ≈ 14,6 GB (GPU, fișierele cu legături fixe numărate o dată; Explorer arată ≈ 22 GB). Verificare: `.venv\Scripts\dubla.exe kontrol`.

Cerințe, ordinea pașilor, harta mediilor Python, motoare opționale, folosire offline, actualizare, dezinstalare și
erori frecvente (în engleză): **[docs/installation.md](docs/installation.md)**. Linux și macOS nu le-am testat încă. Exemplu: [prezentare de produs dublată în engleză, turcă și arabă pe un Mac cu Apple M4, doar pe CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Utilizare

Aplicația desktop: dublu clic pe `arayuz.cmd` (aplicație web locală: `web.cmd`, doar pe 127.0.0.1). Interfața aplicației e deocamdată în turcă. Din linia de comandă:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Pentru dublare în română folosiți `--ayar genel.hedef_dil=ro` (traducerea în română are nevoie de Codex sau Claude Code). Rezultatele ajung în `cikti/<video>_<time>/`: `dubbed_tr.mp4` (cu eticheta `AI-dubbed`), subtitrările originale `transcript_<lang>.srt` și fișierele JSON de lucru; ultima linie `dubbed_video:` arată calea. Toate setările (în engleză și turcă): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Cum funcționează

1. **Audio:** FFmpeg extrage sunetul; Demucs (MIT), opțional, separă vorbirea de fundal.
2. **Vorbire în text:** faster-whisper large-v3-turbo (MIT) cu timpii cuvintelor din wav2vec2 CTC (engleză MIT, turcă CC BY 4.0); opțional CrisperWhisper 2.0 (necomercial) și alte motoare.
3. **Vorbitori:** 3D-Speaker CAM++ (Apache-2.0) și un model de recunoaștere a genului (Apache-2.0) aleg câte o voce AI pentru fiecare vorbitor.
4. **Traducere:** Codex CLI sau Claude Code CLI dacă sunt instalate și autentificate, altfel Opus-MT local din engleză în turcă (CC BY 4.0); backend-urile API sunt opționale.
5. **Voce și sincronizare:** implicit Supertonic 3 (OpenRAIL-M), opțional VoxCPM2 (Apache-2.0) sau XTTS-v2 (necomercial); fiecare replică e accelerată cel mult de 1,25 ori spre durata segmentului original, iar restul îl preia timpul video, așa că dublajul poate ieși mai lung decât originalul.
6. **Video:** FFmpeg scrie vocea nouă, subtitrări SRT / VTT / ASS și eticheta `AI-dubbed`.

## Măsurători

Calculator de referință: GPU Pascal 4 GB, Windows 10; metoda și toate rândurile în [docs/olcumler.md](docs/olcumler.md).

| Ce | Profil CPU | Profil GPU |
|---|---|---|
| Prima instalare, pași impliciți, de la cap la coadă | ≈ 38 min | ≈ 44 min (pachete 13,7 min) |
| Disc după instalare | ≈ 13,2 GB (suma folderelor) | ≈ 14,6 GB (legături fixe o dată) |
| Dublare de probă de 9 s, traducere offline | 528 s | 376 s |
| Clip în engleză de 30 s, Demucs, traducere Claude Code | – | 744 s |

## Limite

- Fără CrisperWhisper (motorul opțional 13), faster-whisper poate sări vorbire sau poate inventa text nespus în chineză și japoneză (observat: primele ≈ 10 s dintr-un clip în chineză s-au pierdut; un țipăt a devenit un rând lung „ああ…”).
- CI testează doar CPU; calea GPU a fost rulată manual pe o placă Pascal de 4 GB. Plăcile noi (RTX 50), Linux și macOS nu sunt testate; bibliotecile GPU instalate conțin kerneluri de la Pascal la RTX 50, iar Maxwell folosește profilul CPU ([tabel de suport GPU, în engleză](docs/installation.md#1-system-requirements)).
- Traducătorul offline face doar engleză în turcă; alte perechi de limbi au nevoie de Codex / Claude Code CLI sau de un backend API.
- Timpii cuvintelor pentru limbi sursă în afară de engleză și turcă: japoneză și chineză prin `scripts/kur.ps1 -Adim hizalama-diller`, celelalte după o rulare cu `DUBLAJ_CEVRIMICI=1`.
- Netestate încă de la cap la coadă: o instalare reală XTTS-v2, RVC, un bot Telegram legat la un serviciu real și CrisperWhisper 2 Medium; Moonshine e experimental. CrisperWhisper 2.0 Turbo (motorul 13) a fost testat cu audio real pe GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Piese de construcție

Fiecare etapă merge și singură, din linia de comandă sau din Python, iar formatele de fișiere dintre etape sunt documentate
(harta etapelor și JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` oferă aceleași etape ca funcții. Instalați doar ce îi trebuie unei etape, de exemplu
`pip install -e ".[stt,hizalama,cpu]"` pentru subtitrări. Cinci unelte mici construite din aceste piese: [examples/](examples/).

## Familie / proiecte înrudite

| Depozit | Ce este | Cum îl folosește acest depozit |
|---|---|---|
| **DubWorld** (acest depozit) | Flux de dublare video complet local, fiecare etapă poate fi folosită și separat | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Transcriere cuvânt cu cuvânt, cu timpii cuvintelor (CrisperWhisper 2.0 Turbo + aliniere CTC) | Motorul opțional 13: `scripts/kur.ps1 -Adim crisper` instalează modelul prin acel depozit, la un commit fixat (ponderi **necomerciale**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Design de voce și lectură cu VoxCPM2, 8 limbi, voci gata făcute | Motorul de voce opțional `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` instalează la un commit fixat; acest depozit îl apelează printr-un adaptor subțire |

Fiecare depozit-soră are licența, instalarea și issue-urile lui; datorită commit-ului fixat, ansamblul se poate reconstrui cu același rezultat.

## Folosire responsabilă

> **Notă juridică.** Răspunderea deplină pentru conținutul pe care îl prelucrați și îl publicați cu acest program, precum
> și pentru respectarea legilor din țara dumneavoastră și a condițiilor site-urilor și serviciilor pe care le folosiți, vă
> aparține. Programul e oferit „ca atare”, fără nicio garanție (Apache-2.0). Textul complet: [ETHICS.md](ETHICS.md).

- **Drepturi și consimțământ.** Prelucrați doar conținut care vă aparține sau pe care aveți dreptul să-l traduceți și să-l redublați,
  și cereți consimțământul persoanelor care pot fi recunoscute în el.
- **Voci.** Nicio imitare a nimănui. Vocea de referință poate fi doar a dumneavoastră sau a cuiva care și-a dat clar acordul.
- **Etichetați.** Rezultatul poartă eticheta de metadate `AI-dubbed`; păstrați-o și spuneți-le spectatorilor, la vedere,
  că dublajul e făcut cu AI (articolul 50 din Regulamentul UE privind IA; licența Supertonic).
- **Descărcări.** Extra-urile opționale `youtube` (yt-dlp) și `galeri` (gallery-dl) sunt doar pentru conținut care vă aparține sau pe care aveți voie să-l descărcați; se aplică condițiile site-ului și
  legile locale.
- **Motoare necomerciale.** CrisperWhisper 2.0 și XTTS-v2 sunt doar pentru uz necomercial (dezactivate implicit). Înainte de o lucrare plătită sau pentru un client,
  verificați coloana **Commercial?** din [THIRD_PARTY.md](THIRD_PARTY.md).
  Modelele de timp al cuvintelor pentru audio sursă fr / de / es / it (CC BY-NC 4.0) sunt și ele necomerciale și cer acordul la prima folosire.

## Ajutor și suport

Întrebări, idei și rezultatele dumneavoastră: [forum de discuții](https://github.com/alexturkey/dubworld/discussions). Problemă la instalare: [raportați o problemă de instalare](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); erori: [raportați o eroare](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(scrieți sistemul de operare, GPU-ul, comanda rulată și ultimele rânduri ale ieșirii). Probleme de securitate: vedeți SECURITY.md, nu într-un issue public.

## Licență și mulțumiri

Cod: Apache-2.0 (LICENSE). Componente externe și licențele lor: THIRD_PARTY.md. Folosire responsabilă: ETHICS.md.
Confidențialitate (ce rămâne pe calculatorul dumneavoastră, ce primește un backend din cloud): PRIVACY.md. Raportări de securitate: SECURITY.md. Schimbări: CHANGELOG.md.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
