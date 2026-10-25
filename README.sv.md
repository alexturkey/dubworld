# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · Svenska · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld dubbar dina videor till ett annat språk direkt på din egen dator, utan att ladda upp dem till någon onlinetjänst: tal blir text med tiden för varje ord, texten översätts och läses upp av en konstgjord (AI-)röst som håller takten med originalet (talet snabbas upp högst 1,25 gånger, resten av skillnaden tas upp av en lätt ändring av videons tempo), undertexter läggs till och en ny video skapas. Standardspråket är turkiska; svenska och andra språk beror på vilken röstmotor du väljer ([docs/diller.md](docs/diller.md)).

## Låt din AI-assistent installera det

Du behöver inte kunna programmera. Öppna en AI-assistent som kan köra kommandon på din dator (Claude Code, Codex,
Gemini CLI eller liknande) och klistra in den här enda meningen:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Assistenten tittar på din dator (grafikkort, processor, minne, disk) och frågar bara en gång, med enkla ord, vilken
installation du vill ha: snabb, rekommenderad för din dator eller fullständig. Den förklarar varje del (vad den gör, hur mycket
plats den tar, hur lång tid det tar, vilken licens den har) och frågar, med början i standardrösten, om du godkänner
användarvillkoren för de valda delarna. Sedan installerar den allt, gör en provdubbning och öppnar programfönstret.
Första stegen och vanliga problem, enkelt förklarat (på engelska): **[docs/getting-started.md](docs/getting-started.md)**.

**Licenser i korthet:** koden Apache-2.0. Standardmodeller: rösten Supertonic 3 under OpenRAIL-M (användningsbegränsningar, godkänns en gång); Opus-MT och den turkiska ordtidsmodellen under CC BY 4.0 (erkännande krävs, NOTICE); FFmpeg-bygget GPL-3.0 (separat program). Endast för icke-kommersiell användning och avstängda som standard: CrisperWhisper 2.0, XTTS-v2 och WhisperX-ordtidsmodellerna för fr / de / es / it. Repot innehåller inga modellvikter ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Snabbinstallation

Windows 10/11 x64; Python, CUDA eller ffmpeg behöver inte vara installerade i förväg. Dubbelklicka på **`kur.cmd`** (eller kör
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); GPU- eller CPU-profil väljs automatiskt
(`-Cpu` tvingar CPU). Dubbelklicka sedan på `arayuz.cmd` för att öppna appen.
Allt stannar i repomappen (`.venv`, `runtime_assets/`); varje nedladdning har låst version och
kontrolleras med sha256. Ledigt utrymme för att börja: 22 GB med GPU-profil, 14 GB med bara CPU; uppmätt användning efter installation ≈ 14,6 GB (GPU, hårdlänkade filer räknade en gång; Utforskaren visar ≈ 22 GB). Kontroll: `.venv\Scripts\dubla.exe kontrol`.

Krav, stegens ordning, karta över Python-miljöerna, valfria motorer, offlineanvändning, uppdatering, avinstallation och
vanliga fel (på engelska): **[docs/installation.md](docs/installation.md)**. Linux och macOS har vi inte testat än. Exempel: [produktvisning dubbad till engelska, turkiska och arabiska på en Mac med Apple M4, bara med CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Användning

Skrivbordsapp: dubbelklicka på `arayuz.cmd` (lokal webbapp: `web.cmd`, bara på 127.0.0.1). Appens gränssnitt är än så länge på turkiska. Från kommandoraden:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

För att dubba till svenska använder du `--ayar genel.hedef_dil=sv` (översättning till svenska kräver Codex eller Claude Code). Resultaten hamnar i `cikti/<video>_<time>/`: `dubbed_tr.mp4` (med taggen `AI-dubbed`), originalundertexterna `transcript_<lang>.srt` och arbetsfilerna i JSON; sista raden `dubbed_video:` visar sökvägen. Alla inställningar (på engelska och turkiska): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Så fungerar det

1. **Ljud:** FFmpeg plockar ut ljudet; valfria Demucs (MIT) skiljer talet från bakgrunden.
2. **Tal till text:** faster-whisper large-v3-turbo (MIT) med ordtider från wav2vec2 CTC (engelska MIT, turkiska CC BY 4.0); valfritt CrisperWhisper 2.0 (icke-kommersiell) och andra motorer.
3. **Talare:** 3D-Speaker CAM++ (Apache-2.0) och en modell som känner igen kön (Apache-2.0) väljer en AI-röst för varje talare.
4. **Översättning:** Codex CLI eller Claude Code CLI om de är installerade och inloggade, annars lokal Opus-MT från engelska till turkiska (CC BY 4.0); API-backends är valfria.
5. **Röst och timing:** standard Supertonic 3 (OpenRAIL-M), valfritt VoxCPM2 (Apache-2.0) eller XTTS-v2 (icke-kommersiell); varje replik snabbas upp högst 1,25 gånger mot originalsegmentets tid och resten sköts av videons tid, så dubben kan bli längre än originalet.
6. **Video:** FFmpeg skriver den nya rösten, undertexter i SRT / VTT / ASS och taggen `AI-dubbed`.

## Mätningar

Referensdator: Pascal-GPU 4 GB, Windows 10; metod och alla rader i [docs/olcumler.md](docs/olcumler.md).

| Vad | CPU-profil | GPU-profil |
|---|---|---|
| Första installationen, standardsteg, från början till slut | ≈ 38 min | ≈ 44 min (paket 13,7 min) |
| Disk efter installation | ≈ 13,2 GB (summa av mappar) | ≈ 14,6 GB (hårdlänkar en gång) |
| Provdubbning 9 s, offlineöversättning | 528 s | 376 s |
| Engelskt klipp 30 s, Demucs, översättning med Claude Code | – | 744 s |

## Begränsningar

- Utan CrisperWhisper (valfri motor 13) kan faster-whisper på kinesiska och japanska hoppa över tal eller hitta på text som ingen sa (sett: de första ≈ 10 s av ett kinesiskt klipp föll bort; ett skrik blev en lång rad ”ああ…”).
- CI testar bara CPU; GPU-vägen kördes för hand på ett Pascal-kort på 4 GB. Nya kort (RTX 50), Linux och macOS är otestade; de GPU-bibliotek som installeras har kärnor från Pascal till RTX 50, och Maxwell använder CPU-profilen ([tabell över GPU-stöd, på engelska](docs/installation.md#1-system-requirements)).
- Offlineöversättaren kan bara engelska till turkiska; andra språkpar kräver Codex / Claude Code CLI eller en API-backend.
- Ordtider för andra källspråk än engelska och turkiska: japanska och kinesiska via `scripts/kur.ps1 -Adim hizalama-diller`, övriga efter en körning med `DUBLAJ_CEVRIMICI=1`.
- Ännu inte testat från början till slut: en riktig XTTS-v2-installation, RVC, en Telegram-bot kopplad till en riktig tjänst och CrisperWhisper 2 Medium; Moonshine är experimentell. CrisperWhisper 2.0 Turbo (motor 13) är testad med riktigt ljud på ett GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Byggklossar

Varje steg går att köra för sig, från kommandoraden eller från Python, och filformaten mellan stegen är dokumenterade
(stegkarta och JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` ger samma steg som funktioner. Installera bara det ett steg behöver, till exempel
`pip install -e ".[stt,hizalama,cpu]"` för undertexter. Fem små verktyg byggda av klossarna: [examples/](examples/).

## Familj / relaterade projekt

| Repo | Vad det är | Hur det här repot använder det |
|---|---|---|
| **DubWorld** (det här repot) | Helt lokal kedja för videodubbning, varje steg går också att använda separat | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Ordagrann tal-till-text med ordtider (CrisperWhisper 2.0 Turbo + CTC-justering) | Valfri motor 13: `scripts/kur.ps1 -Adim crisper` installerar modellen via det repot på en låst commit (vikter **icke-kommersiella**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Röstdesign och uppläsning med VoxCPM2, 8 språk, färdiga röster | Valfri röstmotor `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installerar på en låst commit; det här repot anropar den via en tunn adapter |

Varje systerrepo har egen licens, installation och issues; tack vare den låsta commiten kan helheten byggas om med samma resultat.

## Ansvarsfull användning

> **Juridisk information.** Du har hela ansvaret för det innehåll du bearbetar och publicerar med den här programvaran, och
> för att följa lagarna i ditt land och villkoren för de sajter och tjänster du använder. Programvaran tillhandahålls ”i
> befintligt skick”, utan några garantier (Apache-2.0). Fullständig text: [ETHICS.md](ETHICS.md).

- **Rättigheter och samtycke.** Bearbeta bara innehåll som är ditt eller som du har rätt att översätta och dubba om,
  och be om samtycke från igenkännbara personer som syns i det.
- **Röster.** Ingen imitation av någon. En referensröst får bara vara din egen eller någon som tydligt har gett sitt tillstånd.
- **Märk.** Resultatet har metadatataggen `AI-dubbed`; låt den vara kvar och berätta för tittarna på ett synligt sätt
  att dubbningen är gjord med AI (artikel 50 i EU:s AI-förordning; Supertonic-licensen).
- **Nedladdningar.** De valfria tilläggen `youtube` (yt-dlp) och `galeri` (gallery-dl) är bara för innehåll som är ditt eller som du får ladda ner; sajtens villkor och
  din lokala lag gäller.
- **Icke-kommersiella motorer.** CrisperWhisper 2.0 och XTTS-v2 är bara för icke-kommersiell användning (avstängda som standard). Titta i kolumnen **Commercial?** i
  [THIRD_PARTY.md](THIRD_PARTY.md) före betalda uppdrag eller kundarbete.
  Ordtidsmodellerna för källjud på fr / de / es / it (CC BY-NC 4.0) är också icke-kommersiella och ber om samtycke första gången.

## Hjälp och stöd

Frågor, idéer och dina resultat: [diskussionsforum](https://github.com/alexturkey/dubworld/discussions). Installationsproblem: [rapportera installationsproblem](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); buggar: [rapportera en bugg](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(skriv operativsystem, GPU, kommandot du körde och de sista raderna av utdata). Säkerhetsproblem: se SECURITY.md, inte i ett offentligt issue.

## Licens och erkännanden

Kod: Apache-2.0 (LICENSE). Externa delar och deras licenser: THIRD_PARTY.md. Ansvarsfull användning: ETHICS.md.
Integritet (vad som stannar på din dator, vad en molnbackend får): PRIVACY.md. Säkerhetsrapporter: SECURITY.md. Ändringar: CHANGELOG.md.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
