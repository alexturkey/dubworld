# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · Čeština · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld nadabuje vaše videa do jiného jazyka přímo na vašem počítači, bez nahrávání na jakoukoli online službu: převede řeč na text včetně času každého slova, přeloží ho a nechá ho přečíst umělým (AI) hlasem, který drží krok s původním videem (řeč se zrychlí nejvýš 1,25krát, zbytek rozdílu vyrovná jemná změna tempa videa), přidá titulky a vytvoří nové video. Výchozím jazykem je turečtina; čeština a další jazyky závisí na zvoleném hlasovém enginu ([docs/diller.md](docs/diller.md)).

## Nechte instalaci na svém AI asistentovi

Programovat umět nemusíte. Otevřete AI asistenta, který umí spouštět příkazy na vašem počítači (Claude Code, Codex,
Gemini CLI nebo podobný), a vložte tuhle jednu větu:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Asistent prohlédne váš počítač (grafickou kartu, procesor, paměť, disk) a jen jednou, srozumitelně, se zeptá, jakou instalaci
chcete: rychlou, doporučenou pro váš počítač, nebo úplnou. Vysvětlí každou součást (co dělá, kolik zabere místa, jak dlouho
trvá instalace, jakou má licenci) a počínaje výchozím hlasem se zeptá, zda souhlasíte s podmínkami použití vybraných součástí.
Pak vše nainstaluje, udělá ukázkový dabing a otevře okno programu.
První kroky a časté problémy, jednoduše vysvětlené (anglicky): **[docs/getting-started.md](docs/getting-started.md)**.

**Licence v kostce:** kód Apache-2.0. Výchozí modely: hlas Supertonic 3 pod OpenRAIL-M (omezení použití, souhlas jednou); Opus-MT a turecký model časů slov pod CC BY 4.0 (povinné uvedení autora, NOTICE); build FFmpeg GPL-3.0 (samostatný program). Jen pro nekomerční použití a ve výchozím stavu vypnuté: CrisperWhisper 2.0, XTTS-v2 a modely časů slov WhisperX pro fr / de / es / it. Repozitář neobsahuje žádné váhy modelů ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Rychlá instalace

Windows 10/11 x64; Python, CUDA ani ffmpeg předem instalovat nemusíte. Dvakrát klikněte na **`kur.cmd`** (nebo spusťte
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); profil GPU nebo CPU se vybere sám
(`-Cpu` vynutí CPU). Potom dvakrát klikněte na `arayuz.cmd` a aplikace se otevře.
Všechno zůstává ve složce repozitáře (`.venv`, `runtime_assets/`); každé stahování má pevnou verzi a
ověřuje se pomocí sha256. Volné místo na začátek: 22 GB s profilem GPU, 14 GB jen s CPU; naměřené zabrané místo po instalaci ≈ 14,6 GB (GPU, pevné odkazy počítány jednou; Průzkumník ukazuje ≈ 22 GB). Kontrola: `.venv\Scripts\dubla.exe kontrol`.

Požadavky, pořadí kroků, mapa prostředí Pythonu, volitelné enginy, práce offline, aktualizace, odinstalace a
časté chyby (anglicky): **[docs/installation.md](docs/installation.md)**. Linux a macOS jsme zatím nezkoušeli. Příklad: [produktová prohlídka nadabovaná do angličtiny, turečtiny a arabštiny na Macu s Apple M4, jen na CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Použití

Desktopová aplikace: dvojklik na `arayuz.cmd` (lokální webová aplikace: `web.cmd`, jen na 127.0.0.1). Rozhraní aplikace je zatím v turečtině. Z příkazové řádky:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Pro dabing do češtiny použijte `--ayar genel.hedef_dil=cs` (překlad do češtiny vyžaduje Codex nebo Claude Code). Výsledky se uloží do `cikti/<video>_<time>/`: `dubbed_tr.mp4` (se značkou `AI-dubbed`), původní titulky `transcript_<lang>.srt` a pracovní soubory JSON; poslední řádek `dubbed_video:` ukazuje cestu. Všechna nastavení (anglicky a turecky): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Jak to funguje

1. **Zvuk:** FFmpeg vytáhne zvukovou stopu; volitelný Demucs (MIT) oddělí řeč od pozadí.
2. **Řeč na text:** faster-whisper large-v3-turbo (MIT) s časy slov z wav2vec2 CTC (angličtina MIT, turečtina CC BY 4.0); volitelně CrisperWhisper 2.0 (nekomerční) a další enginy.
3. **Mluvčí:** 3D-Speaker CAM++ (Apache-2.0) a model rozpoznání pohlaví (Apache-2.0) přidělí každému mluvčímu jeden AI hlas.
4. **Překlad:** Codex CLI nebo Claude Code CLI, pokud jsou nainstalované a přihlášené, jinak lokální Opus-MT z angličtiny do turečtiny (CC BY 4.0); API backendy jsou volitelné.
5. **Hlas a časování:** výchozí Supertonic 3 (OpenRAIL-M), volitelně VoxCPM2 (Apache-2.0) nebo XTTS-v2 (nekomerční); každá replika se zrychlí nejvýš 1,25krát k délce původního úseku a zbytek vyrovná čas videa, takže dabing může být delší než originál.
6. **Video:** FFmpeg zapíše nový hlas, titulky SRT / VTT / ASS a značku `AI-dubbed`.

## Měření

Referenční počítač: GPU Pascal 4 GB, Windows 10; metodika a všechny řádky v [docs/olcumler.md](docs/olcumler.md).

| Co | Profil CPU | Profil GPU |
|---|---|---|
| První instalace, výchozí kroky, od začátku do konce | ≈ 38 min | ≈ 44 min (balíčky 13,7 min) |
| Disk po instalaci | ≈ 13,2 GB (součet složek) | ≈ 14,6 GB (pevné odkazy jednou) |
| Ukázkový dabing 9 s, offline překlad | 528 s | 376 s |
| Anglický klip 30 s, Demucs, překlad Claude Code | – | 744 s |

## Omezení

- Bez CrisperWhisper (volitelný engine 13) může faster-whisper v čínštině a japonštině vynechat řeč nebo si vymyslet text, který nikdo neřekl (pozorováno: chyběly první ≈ 10 s čínského klipu; z výkřiku se stal dlouhý řádek „ああ…“).
- CI testuje jen CPU; cesta GPU byla spuštěna ručně na kartě Pascal 4 GB. Nové karty (RTX 50), Linux a macOS nejsou vyzkoušené; instalované knihovny GPU obsahují kernely od Pascalu po RTX 50 a Maxwell používá profil CPU ([tabulka podpory GPU, anglicky](docs/installation.md#1-system-requirements)).
- Offline překladač umí jen z angličtiny do turečtiny; jiné jazykové páry potřebují Codex / Claude Code CLI nebo API backend.
- Časy slov pro zdrojové jazyky kromě angličtiny a turečtiny: japonština a čínština přes `scripts/kur.ps1 -Adim hizalama-diller`, ostatní po jednom spuštění s `DUBLAJ_CEVRIMICI=1`.
- Zatím nevyzkoušeno od začátku do konce: skutečná instalace XTTS-v2, RVC, telegramový bot napojený na skutečnou službu a CrisperWhisper 2 Medium; Moonshine je experimentální. CrisperWhisper 2.0 Turbo (engine 13) byl vyzkoušen se skutečným zvukem na GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Stavební kostky

Každý krok běží i samostatně, z příkazové řádky nebo z Pythonu, a formáty souborů mezi kroky jsou popsané
(mapa kroků a JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` nabízí stejné kroky jako funkce. Instalujte jen to, co daný krok potřebuje, třeba
`pip install -e ".[stt,hizalama,cpu]"` pro titulky. Pět malých nástrojů postavených z těchto kostek: [examples/](examples/).

## Rodina / související projekty

| Repozitář | Co to je | Jak ho tento repozitář používá |
|---|---|---|
| **DubWorld** (tento repozitář) | Plně lokální řetězec pro dabing videa, každý krok jde použít i zvlášť | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Doslovný převod řeči na text s časy slov (CrisperWhisper 2.0 Turbo + zarovnání CTC) | Volitelný engine 13: `scripts/kur.ps1 -Adim crisper` nainstaluje model přes onen repozitář na pevném commitu (váhy **nekomerční**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Návrh hlasu a čtení s VoxCPM2, 8 jazyků, hotové hlasy | Volitelný hlasový engine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` instaluje na pevném commitu; tento repozitář ho volá přes tenký adaptér |

Každý sesterský repozitář má vlastní licenci, instalaci a issues; díky pevnému commitu jde celek znovu sestavit se stejným výsledkem.

## Odpovědné používání

> **Právní upozornění.** Plnou odpovědnost za obsah, který s tímto softwarem zpracujete a zveřejníte, i za dodržení zákonů
> vaší země a podmínek webů a služeb, které používáte, nesete vy. Software se poskytuje „tak, jak je“, bez jakékoli záruky
> (Apache-2.0). Plné znění: [ETHICS.md](ETHICS.md).

- **Práva a souhlas.** Zpracovávejte jen obsah, který je váš nebo který smíte přeložit a znovu nadabovat,
  a požádejte o souhlas lidi, kteří jsou v něm rozpoznatelní.
- **Hlasy.** Žádné vydávání se za někoho jiného. Referenční hlas smí být jen váš nebo člověka, který k tomu dal jasný souhlas.
- **Označujte.** Výsledek nese metadatovou značku `AI-dubbed`; nechte ji tam a dejte divákům viditelně vědět,
  že dabing vznikl pomocí AI (čl. 50 AI Actu EU; licence Supertonic).
- **Stahování.** Volitelné doplňky `youtube` (yt-dlp) a `galeri` (gallery-dl) jsou jen pro obsah, který je váš nebo který smíte stáhnout; platí podmínky webu a
  vaše místní zákony.
- **Nekomerční enginy.** CrisperWhisper 2.0 a XTTS-v2 jsou jen pro nekomerční použití (ve výchozím stavu vypnuté). Před placenou zakázkou nebo prací pro klienta
  se podívejte do sloupce **Commercial?** v [THIRD_PARTY.md](THIRD_PARTY.md).
  Modely časů slov pro zdrojový zvuk fr / de / es / it (CC BY-NC 4.0) jsou také nekomerční a při prvním použití žádají o souhlas.

## Pomoc a podpora

Dotazy, nápady a vaše výsledky: [diskusní fórum](https://github.com/alexturkey/dubworld/discussions). Problém s instalací: [nahlásit problém s instalací](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); chyby: [nahlásit chybu](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(uveďte systém, GPU, spuštěný příkaz a poslední řádky výstupu). Bezpečnostní problémy: viz SECURITY.md, ne ve veřejném issue.

## Licence a poděkování

Kód: Apache-2.0 (LICENSE). Součásti třetích stran a jejich licence: THIRD_PARTY.md. Odpovědné používání: ETHICS.md.
Soukromí (co zůstává na vašem počítači, co dostane cloudový backend): PRIVACY.md. Hlášení zranitelností: SECURITY.md. Změny: CHANGELOG.md.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
