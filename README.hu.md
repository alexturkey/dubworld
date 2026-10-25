# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · Magyar · [Svenska](README.sv.md)

> A DubWorld a saját gépeden szinkronizálja más nyelvre a videóidat, anélkül hogy bármilyen online szolgáltatásba feltöltené őket: a beszédet szöveggé alakítja minden szó időpontjával, lefordítja, majd egy mesterséges (MI-) hanggal felolvastatja úgy, hogy lépést tartson az eredeti videóval (a beszéd legfeljebb 1,25-szörösre gyorsul, a maradék eltérést a videó tempójának enyhe módosítása veszi fel), feliratot tesz rá, és új videót készít. Az alapértelmezett nyelv a török; a magyar és a többi nyelv a választott hangmotortól függ ([docs/diller.md](docs/diller.md)).

## Telepíttesd az MI-asszisztenseddel

Programozni nem kell tudnod. Nyiss meg egy MI-asszisztenst, amely parancsokat tud futtatni a gépeden (Claude Code, Codex,
Gemini CLI vagy hasonló), és illeszd be ezt az egy mondatot:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Az asszisztens átnézi a gépedet (videokártya, processzor, memória, lemez), és csak egyszer, közérthetően kérdezi meg, milyen
telepítést szeretnél: gyorsat, a gépedhez ajánlottat vagy teljeset. Minden részt elmagyaráz (mit csinál, mennyi helyet foglal,
mennyi ideig tart, milyen licence van), és az alapértelmezett hanggal kezdve megkérdezi, elfogadod-e a kiválasztott részek
felhasználási feltételeit. Ezután telepít, készít egy próbaszinkront, és megnyitja a program ablakát.
Első lépések és gyakori gondok, egyszerűen elmagyarázva (angolul): **[docs/getting-started.md](docs/getting-started.md)**.

**Licencek röviden:** a kód Apache-2.0. Alapértelmezett modellek: a Supertonic 3 hang OpenRAIL-M alatt (használati korlátozások, egyszer kell elfogadni); az Opus-MT és a török szóidő-modell CC BY 4.0 alatt (kötelező a forrásmegjelölés, NOTICE); az FFmpeg build GPL-3.0 (külön program). Csak nem kereskedelmi célra és alapból kikapcsolva: CrisperWhisper 2.0, XTTS-v2 és a WhisperX szóidő-modellek fr / de / es / it nyelvre. A tárolóban nincs egyetlen modellsúly sem ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Gyors telepítés

Windows 10/11 x64; nem kell előre telepített Python, CUDA vagy ffmpeg. Kattints duplán a **`kur.cmd`** fájlra (vagy futtasd:
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); a GPU- vagy CPU-profil magától választódik ki
(a `-Cpu` kikényszeríti a CPU-t). Utána kattints duplán az `arayuz.cmd` fájlra, és megnyílik az alkalmazás.
Minden a tároló mappájában marad (`.venv`, `runtime_assets/`); minden letöltés rögzített verziójú, és
sha256-tal ellenőrzött. Induláshoz szükséges szabad hely: 22 GB GPU-profillal, 14 GB csak CPU-val; mért foglalás telepítés után ≈ 14,6 GB (GPU, a hardlinkelt fájlok egyszer számolva; a Fájlkezelő ≈ 22 GB-ot mutat). Ellenőrzés: `.venv\Scripts\dubla.exe kontrol`.

Követelmények, a lépések sorrendje, a Python-környezetek térképe, választható motorok, offline használat, frissítés, eltávolítás és
gyakori hibák (angolul): **[docs/installation.md](docs/installation.md)**. Linuxon és macOS-en még nem teszteltük. Példa: [angolra, törökre és arabra szinkronizált termékbemutató Apple M4-es Macen, csak CPU-val](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Használat

Asztali alkalmazás: dupla kattintás az `arayuz.cmd` fájlra (helyi webalkalmazás: `web.cmd`, csak a 127.0.0.1 címen). Az alkalmazás felülete egyelőre török nyelvű. Parancssorból:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Magyar szinkronhoz használd a `--ayar genel.hedef_dil=hu` beállítást (a magyar fordításhoz Codex vagy Claude Code kell). Az eredmények a `cikti/<video>_<time>/` mappába kerülnek: `dubbed_tr.mp4` (`AI-dubbed` címkével), az eredeti felirat `transcript_<lang>.srt` és a munka-JSON-fájlok; az utolsó `dubbed_video:` sor mutatja az útvonalat. Minden beállítás (angolul és törökül): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Hogyan működik

1. **Hang:** az FFmpeg kiveszi a hangsávot; a választható Demucs (MIT) leválasztja a beszédet a háttérről.
2. **Beszédből szöveg:** faster-whisper large-v3-turbo (MIT) wav2vec2 CTC szóidőkkel (angol MIT, török CC BY 4.0); választhatóan CrisperWhisper 2.0 (nem kereskedelmi) és más motorok.
3. **Beszélők:** a 3D-Speaker CAM++ (Apache-2.0) és egy nemfelismerő modell (Apache-2.0) minden beszélőhöz egy MI-hangot választ.
4. **Fordítás:** Codex CLI vagy Claude Code CLI, ha telepítve van és be vagy jelentkezve, különben helyi Opus-MT angolról törökre (CC BY 4.0); az API-háttérrendszerek választhatók.
5. **Hang és időzítés:** alapból Supertonic 3 (OpenRAIL-M), választhatóan VoxCPM2 (Apache-2.0) vagy XTTS-v2 (nem kereskedelmi); minden mondat legfeljebb 1,25-szörösre gyorsul az eredeti szakasz hossza felé, a maradékot a videó ideje veszi fel, így a szinkron hosszabb lehet az eredetinél.
6. **Videó:** az FFmpeg beírja az új hangot, az SRT / VTT / ASS feliratot és az `AI-dubbed` címkét.

## Mérések

Referenciagép: 4 GB-os Pascal GPU, Windows 10; módszer és minden sor: [docs/olcumler.md](docs/olcumler.md).

| Mi | CPU-profil | GPU-profil |
|---|---|---|
| Első telepítés, alapértelmezett lépések, elejétől a végéig | ≈ 38 perc | ≈ 44 perc (csomagok 13,7 perc) |
| Lemez telepítés után | ≈ 13,2 GB (mappák összege) | ≈ 14,6 GB (hardlinkek egyszer) |
| 9 mp-es próbaszinkron, offline fordítás | 528 mp | 376 mp |
| 30 mp-es angol klip, Demucs, Claude Code fordítás | – | 744 mp |

## Korlátok

- CrisperWhisper (választható 13-as motor) nélkül a faster-whisper kínaiban és japánban kihagyhat beszédet, vagy kitalálhat el nem hangzott szöveget (megfigyelve: egy kínai klip első ≈ 10 mp-e elveszett; egy kiáltásból hosszú „ああ…” sor lett).
- A CI csak CPU-t tesztel; a GPU-ágat kézzel futtattuk egy 4 GB-os Pascal kártyán. Az új kártyák (RTX 50), a Linux és a macOS nincs kipróbálva; a telepített GPU-könyvtárakban Pascaltól RTX 50-ig vannak kernelek, a Maxwell pedig a CPU-profilt használja ([GPU-támogatási táblázat, angolul](docs/installation.md#1-system-requirements)).
- Az offline fordító csak angolról törökre fordít; más nyelvpárokhoz Codex / Claude Code CLI vagy API-háttérrendszer kell.
- Szóidők az angoltól és töröktől eltérő forrásnyelvekhez: japán és kínai a `scripts/kur.ps1 -Adim hizalama-diller` paranccsal, a többi egyszeri `DUBLAJ_CEVRIMICI=1` futtatás után.
- Még nincs végigpróbálva: valódi XTTS-v2-telepítés, RVC, valódi szolgáltatáshoz kötött Telegram-bot és CrisperWhisper 2 Medium; a Moonshine kísérleti. A CrisperWhisper 2.0 Turbót (13-as motor) valódi hanggal teszteltük GTX 1050 Ti 4 GB-on (tr, en, ja; ≈ 1,4 GB VRAM).

## Építőkockák

Minden lépés önállóan is fut, parancssorból vagy Pythonból, a lépések közötti fájlformátumok pedig dokumentáltak
(lépéstérkép és JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

A `from dublaj_hatti import api` ugyanezeket a lépéseket függvényként adja. Csak azt telepítsd, ami egy lépéshez kell, például
`pip install -e ".[stt,hizalama,cpu]"` a feliratokhoz. Öt kis eszköz ezekből a kockákból: [examples/](examples/).

## Család / kapcsolódó projektek

| Tároló | Mi ez | Hogyan használja ez a tároló |
|---|---|---|
| **DubWorld** (ez a tároló) | Teljesen helyi videószinkron-folyamat, minden lépése külön is használható | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Szó szerinti beszéd-szöveg átírás szóidőkkel (CrisperWhisper 2.0 Turbo + CTC-illesztés) | Választható 13-as motor: a `scripts/kur.ps1 -Adim crisper` azon a tárolón át, rögzített commiton telepíti a modellt (súlyok **nem kereskedelmi** célra) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Hangtervezés és felolvasás VoxCPM2-vel, 8 nyelv, kész hangok | Választható hangmotor `voxcpm2`: a `scripts/kur.ps1 -Adim voxcpm2` rögzített commiton telepíti; ez a tároló vékony adapterrel hívja |

Minden testvértárolónak saját licence, telepítése és issue-i vannak; a rögzített commit miatt az egész ugyanazzal az eredménnyel újraépíthető.

## Felelős használat

> **Jogi tudnivaló.** A teljes felelősség téged terhel azért a tartalomért, amelyet ezzel a szoftverrel feldolgozol és
> közzéteszel, valamint azért, hogy betartsd az országod törvényeit és a használt oldalak és szolgáltatások feltételeit. A
> szoftvert „ahogy van” adjuk, mindenféle garancia nélkül (Apache-2.0). Teljes szöveg: [ETHICS.md](ETHICS.md).

- **Jogok és hozzájárulás.** Csak olyan tartalmat dolgozz fel, amely a tiéd, vagy amelynek fordítására és újraszinkronizálására jogod van,
  és kérd a felismerhető szereplők hozzájárulását.
- **Hangok.** Senkit ne utánozz. Referenciahang csak a sajátod lehet, vagy olyasvalakié, aki ehhez egyértelműen hozzájárult.
- **Jelöld.** Az eredmény `AI-dubbed` metaadat-címkét kap; hagyd rajta, és jól láthatóan mondd el a nézőidnek,
  hogy a szinkron MI-vel készült (az EU MI-rendelet 50. cikke; Supertonic-licenc).
- **Letöltések.** A választható `youtube` (yt-dlp) és `galeri` (gallery-dl) kiegészítők csak saját vagy jogosan letölthető tartalomhoz valók; az oldal feltételei és
  a helyi jog érvényes.
- **Nem kereskedelmi motorok.** A CrisperWhisper 2.0 és az XTTS-v2 csak nem kereskedelmi célra használható (alapból kikapcsolva). Fizetős vagy ügyfélmunka előtt
  nézd meg a [THIRD_PARTY.md](THIRD_PARTY.md) **Commercial?** oszlopát.
  A fr / de / es / it forráshanghoz tartozó szóidő-modellek (CC BY-NC 4.0) szintén nem kereskedelmiek, és első használatkor hozzájárulást kérnek.

## Segítség és támogatás

Kérdések, ötletek és az eredményeid: [beszélgetőfórum](https://github.com/alexturkey/dubworld/discussions). Telepítési gond: [telepítési probléma bejelentése](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); hibák: [hiba bejelentése](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(írd meg az operációs rendszert, a GPU-t, a futtatott parancsot és a kimenet utolsó sorait). Biztonsági ügyek: lásd SECURITY.md, ne nyilvános issue-ban.

## Licenc és köszönetnyilvánítás

Kód: Apache-2.0 (LICENSE). Külső összetevők és licenceik: THIRD_PARTY.md. Felelős használat: ETHICS.md.
Adatvédelem (mi marad a gépeden, mit kap egy felhős háttérrendszer): PRIVACY.md. Biztonsági bejelentések: SECURITY.md. Változások: CHANGELOG.md.

<!-- i18n-source: README.md sha256:2750a34df58c -->
