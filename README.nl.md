# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · Nederlands · [Українська](README.uk.md)

> DubWorld dubt je video's naar een andere taal, gewoon op je eigen computer, zonder ze naar een online dienst te uploaden: het zet spraak om in tekst met de tijd van elk woord, vertaalt die en laat een kunstmatige (AI-)stem hem uitspreken die gelijk blijft lopen met het origineel (spraak wordt hooguit 1,25 keer versneld, de rest van het verschil vangt een lichte tempowijziging van de video op), voegt ondertitels toe en maakt er een nieuwe video van. De standaardtaal is Turks; Nederlands en andere talen hangen af van de gekozen stemengine ([docs/diller.md](docs/diller.md)).

## Laat je AI-assistent het installeren

Je hoeft niet te kunnen programmeren. Open een AI-assistent die opdrachten op je computer kan uitvoeren (Claude Code, Codex,
Gemini CLI of iets vergelijkbaars) en plak deze ene zin:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

De assistent bekijkt je computer (videokaart, processor, geheugen, schijf) en vraagt maar één keer, in gewone taal, welke
installatie je wilt: snel, aangeraden voor jouw computer, of volledig. Hij legt elk onderdeel uit (wat het doet, hoeveel
schijfruimte het kost, hoe lang het duurt, welke licentie het heeft) en vraagt, te beginnen bij de standaardstem, of je de
gebruiksvoorwaarden van de gekozen onderdelen accepteert. Daarna installeert hij alles, maakt een voorbeelddub en opent het programmavenster.
Eerste stappen en veelvoorkomende problemen, eenvoudig uitgelegd (in het Engels): **[docs/getting-started.md](docs/getting-started.md)**.

**Licenties in het kort:** code Apache-2.0. Standaardmodellen: stem Supertonic 3 onder OpenRAIL-M (gebruiksbeperkingen, één keer geaccepteerd); Opus-MT en het Turkse woordtijdmodel onder CC BY 4.0 (naamsvermelding verplicht, NOTICE); FFmpeg-build GPL-3.0 (apart programma). Alleen voor niet-commercieel gebruik en standaard uit: CrisperWhisper 2.0, XTTS-v2 en de WhisperX-woordtijdmodellen voor fr / de / es / it. Deze repository bevat geen enkel modelgewicht ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Snel installeren

Windows 10/11 x64; Python, CUDA of ffmpeg hoeven niet vooraf geïnstalleerd te zijn. Dubbelklik op **`kur.cmd`** (of voer
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` uit); het GPU- of CPU-profiel wordt vanzelf gekozen
(`-Cpu` dwingt CPU af). Dubbelklik daarna op `arayuz.cmd` om de app te openen.
Alles blijft in de repositorymap (`.venv`, `runtime_assets/`); elke download heeft een vaste versie en wordt
gecontroleerd met sha256. Vrije ruimte om te beginnen: 22 GB met het GPU-profiel, 14 GB met alleen CPU; gemeten gebruik na installatie ≈ 14,6 GB (GPU, hardgelinkte bestanden één keer geteld; Verkenner toont ≈ 22 GB). Controleren: `.venv\Scripts\dubla.exe kontrol`.

Vereisten, volgorde van de stappen, overzicht van de Python-omgevingen, optionele engines, offline gebruik, bijwerken, verwijderen en
veelvoorkomende fouten (in het Engels): **[docs/installation.md](docs/installation.md)**. Linux en macOS hebben we nog niet getest. Voorbeeld: [producttour gedubd in het Engels, Turks en Arabisch op een Apple M4-Mac, alleen met CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Gebruik

Desktopapp: dubbelklik op `arayuz.cmd` (lokale webapp: `web.cmd`, alleen op 127.0.0.1). De interface van de app is voorlopig in het Turks. Vanaf de opdrachtregel:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Om naar het Nederlands te dubben gebruik je `--ayar genel.hedef_dil=nl` (vertalen naar het Nederlands vraagt Codex of Claude Code). De resultaten komen in `cikti/<video>_<time>/`: `dubbed_tr.mp4` (met de tag `AI-dubbed`), de originele ondertitels `transcript_<lang>.srt` en de JSON-werkbestanden; de laatste regel `dubbed_video:` geeft het pad. Alle instellingen (in het Engels en Turks): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Hoe het werkt

1. **Audio:** FFmpeg haalt het geluid eruit; optioneel scheidt Demucs (MIT) de spraak van de achtergrond.
2. **Spraak naar tekst:** faster-whisper large-v3-turbo (MIT) met woordtijden van wav2vec2 CTC (Engels MIT, Turks CC BY 4.0); optioneel CrisperWhisper 2.0 (niet-commercieel) en andere engines.
3. **Sprekers:** 3D-Speaker CAM++ (Apache-2.0) en een model dat geslacht herkent (Apache-2.0) kiezen voor elke spreker één AI-stem.
4. **Vertaling:** Codex CLI of Claude Code CLI als die geïnstalleerd en ingelogd is, anders lokaal Opus-MT van Engels naar Turks (CC BY 4.0); API-backends zijn optioneel.
5. **Stem en timing:** standaard Supertonic 3 (OpenRAIL-M), optioneel VoxCPM2 (Apache-2.0) of XTTS-v2 (niet-commercieel); elke zin wordt hooguit 1,25 keer versneld richting de tijd van het originele fragment, de rest regelt de videotijd, dus de dub kan langer zijn dan het origineel.
6. **Video:** FFmpeg schrijft de nieuwe stem, ondertitels in SRT / VTT / ASS en de tag `AI-dubbed`.

## Metingen

Referentiecomputer: Pascal-GPU 4 GB, Windows 10; methode en alle rijen in [docs/olcumler.md](docs/olcumler.md).

| Wat | CPU-profiel | GPU-profiel |
|---|---|---|
| Eerste installatie, standaardstappen, van begin tot eind | ≈ 38 min | ≈ 44 min (pakketten 13,7 min) |
| Schijf na installatie | ≈ 13,2 GB (som van mappen) | ≈ 14,6 GB (hardlinks één keer geteld) |
| Voorbeelddub van 9 s, offline vertaling | 528 s | 376 s |
| Engelse clip van 30 s, Demucs, vertaling met Claude Code | – | 744 s |

## Beperkingen

- Zonder CrisperWhisper (optionele engine 13) kan faster-whisper in het Chinees en Japans spraak overslaan of tekst verzinnen die niemand zei (gezien: de eerste ≈ 10 s van een Chinese clip ontbraken; een schreeuw werd een lange regel „ああ…”).
- CI test alleen CPU; het GPU-pad is met de hand gedraaid op een Pascal-kaart van 4 GB. Nieuwe kaarten (RTX 50), Linux en macOS zijn niet getest; de geïnstalleerde GPU-bibliotheken bevatten kernels van Pascal tot RTX 50, en Maxwell gebruikt het CPU-profiel ([tabel GPU-ondersteuning, in het Engels](docs/installation.md#1-system-requirements)).
- De offline vertaler kan alleen Engels naar Turks; andere taalparen hebben Codex / Claude Code CLI of een API-backend nodig.
- Woordtijden voor brontalen anders dan Engels en Turks: Japans en Chinees via `scripts/kur.ps1 -Adim hizalama-diller`, de andere na één keer draaien met `DUBLAJ_CEVRIMICI=1`.
- Nog niet van begin tot eind getest: een echte XTTS-v2-installatie, RVC, een Telegram-bot gekoppeld aan een echte dienst en CrisperWhisper 2 Medium; Moonshine is experimenteel. CrisperWhisper 2.0 Turbo (engine 13) is met echte audio getest op een GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Bouwstenen

Elke stap werkt ook los, vanaf de opdrachtregel of vanuit Python, en de bestandsformaten tussen de stappen zijn beschreven
(stappenkaart en JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` biedt dezelfde stappen als functies. Installeer alleen wat een stap nodig heeft, bijvoorbeeld
`pip install -e ".[stt,hizalama,cpu]"` voor ondertitels. Vijf kleine tools gebouwd met deze bouwstenen: [examples/](examples/).

## Familie / verwante projecten

| Repository | Wat het is | Hoe deze repository het gebruikt |
|---|---|---|
| **DubWorld** (deze repository) | Volledig lokale pijplijn voor videodubbing, elke stap ook los te gebruiken | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Letterlijke spraak-naar-tekst met woordtijden (CrisperWhisper 2.0 Turbo + CTC-uitlijning) | Optionele engine 13: `scripts/kur.ps1 -Adim crisper` installeert het model via die repository op een vaste commit (gewichten **niet-commercieel**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Stemontwerp en voorlezen met VoxCPM2, 8 talen, kant-en-klare stemmen | Optionele stemengine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installeert op een vaste commit; deze repository roept het aan via een dunne adapter |

Elke zusterrepository heeft een eigen licentie, installatie en issues; door de vaste commit is het geheel opnieuw te bouwen met hetzelfde resultaat.

## Verantwoord gebruik

> **Juridische mededeling.** Jij bent volledig verantwoordelijk voor de inhoud die je met deze software verwerkt en publiceert,
> en voor het naleven van de wetten in jouw land en de voorwaarden van de sites en diensten die je gebruikt. De software wordt
> geleverd „zoals hij is”, zonder enige garantie (Apache-2.0). Volledige tekst: [ETHICS.md](ETHICS.md).

- **Rechten en toestemming.** Verwerk alleen inhoud die van jou is of die je mag vertalen en opnieuw mag dubben,
  en vraag toestemming aan herkenbare mensen die erin voorkomen.
- **Stemmen.** Geen imitatie van wie dan ook. Een referentiestem mag alleen je eigen stem zijn of die van iemand die duidelijk toestemming gaf.
- **Labelen.** Het resultaat draagt de metadatatag `AI-dubbed`; laat die staan en vertel je kijkers op een zichtbare manier
  dat de dub met AI is gemaakt (artikel 50 EU AI Act; Supertonic-licentie).
- **Downloads.** De optionele extra's `youtube` (yt-dlp) en `galeri` (gallery-dl) zijn alleen voor inhoud die van jou is of die je mag downloaden; de voorwaarden van de site en
  jouw lokale wetgeving gelden.
- **Niet-commerciële engines.** CrisperWhisper 2.0 en XTTS-v2 zijn alleen voor niet-commercieel gebruik (standaard uit). Kijk vóór betaald werk of werk voor klanten
  in de kolom **Commercial?** van [THIRD_PARTY.md](THIRD_PARTY.md).
  De woordtijdmodellen voor bronaudio in fr / de / es / it (CC BY-NC 4.0) zijn ook niet-commercieel en vragen bij het eerste gebruik om toestemming.

## Hulp en ondersteuning

Vragen, ideeën en je resultaten: [discussieforum](https://github.com/alexturkey/dubworld/discussions). Installatieprobleem: [installatieprobleem melden](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); bugs: [bug melden](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(vermeld besturingssysteem, GPU, de uitgevoerde opdracht en de laatste regels van de uitvoer). Beveiligingsproblemen: zie SECURITY.md, niet in een openbaar issue.

## Licentie en vermelding

Code: Apache-2.0 (LICENSE). Externe onderdelen en hun licenties: THIRD_PARTY.md. Verantwoord gebruik: ETHICS.md.
Privacy (wat op je computer blijft, wat een cloudbackend ontvangt): PRIVACY.md. Beveiligingsmeldingen: SECURITY.md. Wijzigingen: CHANGELOG.md.

<!-- i18n-source: README.md sha256:9622edb95c84 -->
