# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · Polski · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md)

> DubWorld dubbinguje Twoje filmy na inny język bezpośrednio na Twoim komputerze, bez wysyłania ich do jakiejkolwiek usługi w sieci: zamienia mowę na tekst razem z czasem każdego słowa, tłumaczy go, a potem czyta go sztucznym głosem (AI), który trzyma się oryginalnego obrazu (mowa jest przyspieszana najwyżej 1,25 raza, resztę różnicy wyrównuje delikatna zmiana tempa wideo), dodaje napisy i tworzy nowy film. Domyślnym językiem jest turecki; polski i inne języki zależą od wybranego silnika głosu ([docs/diller.md](docs/diller.md)).

## Niech asystent AI zainstaluje to za Ciebie

Nie musisz umieć programować. Otwórz asystenta AI, który potrafi uruchamiać polecenia na Twoim komputerze (Claude Code, Codex,
Gemini CLI lub podobny), i wklej to jedno zdanie:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

Asystent sprawdzi Twój komputer (kartę graficzną, procesor, pamięć, dysk) i tylko raz, prostymi słowami, zapyta, jakiej
instalacji chcesz: szybkiej, dopasowanej do Twojego sprzętu czy pełnej. Opisze każdy składnik (co robi, ile zajmuje miejsca,
ile trwa instalacja, na jakiej jest licencji) i, zaczynając od domyślnego głosu, zapyta, czy akceptujesz warunki użycia
wybranych składników. Potem zainstaluje wszystko, zrobi próbny dubbing i otworzy okno programu.
Pierwsze kroki i najczęstsze problemy, opisane prosto (po angielsku): **[docs/getting-started.md](docs/getting-started.md)**.

**Licencje w skrócie:** kod Apache-2.0. Modele domyślne: głos Supertonic 3 na OpenRAIL-M (ograniczenia użycia, akceptowane raz); Opus-MT i turecki model czasu słów na CC BY 4.0 (wymagane podanie autorstwa, NOTICE); build FFmpeg GPL-3.0 (osobny program). Tylko do użytku niekomercyjnego i domyślnie wyłączone: CrisperWhisper 2.0, XTTS-v2 oraz modele czasu słów WhisperX dla fr / de / es / it. Repozytorium nie zawiera żadnych wag modeli ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Szybka instalacja

Windows 10/11 x64; nie potrzebujesz wcześniej zainstalowanego Pythona, CUDA ani ffmpeg. Kliknij dwukrotnie **`kur.cmd`** (albo uruchom
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); profil GPU lub CPU wybiera się sam
(`-Cpu` wymusza CPU). Potem kliknij dwukrotnie `arayuz.cmd`, żeby otworzyć aplikację.
Wszystko zostaje w folderze repozytorium (`.venv`, `runtime_assets/`); każde pobranie ma przypiętą wersję i jest
sprawdzane sumą sha256. Wolne miejsce na start: 22 GB z profilem GPU, 14 GB tylko z CPU; zmierzone zajęcie po instalacji ≈ 14,6 GB (GPU, pliki z twardymi dowiązaniami liczone raz; Eksplorator plików pokazuje ≈ 22 GB). Sprawdzenie: `.venv\Scripts\dubla.exe kontrol`.

Wymagania, kolejność kroków, mapa środowisk Pythona, opcjonalne silniki, praca offline, aktualizacja, odinstalowanie i
częste błędy (po angielsku): **[docs/installation.md](docs/installation.md)**. Linuksa i macOS jeszcze nie testowaliśmy. Przykład: [prezentacja produktu zdubbingowana po angielsku, turecku i arabsku na Macu z Apple M4, tylko na CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Jak używać

Aplikacja okienkowa: dwuklik na `arayuz.cmd` (lokalna aplikacja webowa: `web.cmd`, tylko na 127.0.0.1). Interfejs aplikacji jest na razie po turecku. Z wiersza poleceń:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Żeby zrobić dubbing po polsku, użyj `--ayar genel.hedef_dil=pl` (tłumaczenie na polski wymaga Codex albo Claude Code). Wyniki trafiają do `cikti/<video>_<time>/`: `dubbed_tr.mp4` (z tagiem `AI-dubbed`), oryginalne napisy `transcript_<lang>.srt` i robocze pliki JSON; ostatnia linia `dubbed_video:` podaje ścieżkę. Wszystkie ustawienia (po angielsku i turecku): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Jak to działa

1. **Dźwięk:** FFmpeg wyciąga ścieżkę dźwiękową; opcjonalny Demucs (MIT) oddziela mowę od tła.
2. **Mowa na tekst:** faster-whisper large-v3-turbo (MIT) z czasami słów z wav2vec2 CTC (angielski MIT, turecki CC BY 4.0); opcjonalnie CrisperWhisper 2.0 (niekomercyjny) i inne silniki.
3. **Mówcy:** 3D-Speaker CAM++ (Apache-2.0) i model rozpoznawania płci (Apache-2.0) przydzielają każdemu mówcy jeden głos AI.
4. **Tłumaczenie:** Codex CLI lub Claude Code CLI, jeśli są zainstalowane i zalogowane, w przeciwnym razie lokalny Opus-MT z angielskiego na turecki (CC BY 4.0); backendy API są opcjonalne.
5. **Głos i czas:** domyślnie Supertonic 3 (OpenRAIL-M), opcjonalnie VoxCPM2 (Apache-2.0) lub XTTS-v2 (niekomercyjny); każda kwestia jest przyspieszana najwyżej 1,25 raza w stronę czasu oryginalnego fragmentu, resztę wyrównuje czas wideo, więc dubbing może być dłuższy od oryginału.
6. **Wideo:** FFmpeg zapisuje nowy głos, napisy SRT / VTT / ASS i tag `AI-dubbed`.

## Pomiary

Komputer odniesienia: GPU Pascal 4 GB, Windows 10; metoda i wszystkie wiersze w [docs/olcumler.md](docs/olcumler.md).

| Co | Profil CPU | Profil GPU |
|---|---|---|
| Pierwsza instalacja, domyślne kroki, od początku do końca | ≈ 38 min | ≈ 44 min (pakiety 13,7 min) |
| Dysk po instalacji | ≈ 13,2 GB (suma folderów) | ≈ 14,6 GB (twarde dowiązania liczone raz) |
| Próbny dubbing 9 s, tłumaczenie offline | 528 s | 376 s |
| Angielski klip 30 s, Demucs, tłumaczenie Claude Code | – | 744 s |

## Ograniczenia

- Bez CrisperWhisper (opcjonalny silnik 13) faster-whisper może w chińskim i japońskim pominąć mowę albo wymyślić tekst, którego nikt nie powiedział (zaobserwowano: zgubione pierwsze ≈ 10 s chińskiego klipu; krzyk zamienił się w długą linię „ああ…”).
- CI testuje tylko CPU; ścieżkę GPU uruchamiano ręcznie na karcie Pascal 4 GB. Nowe karty (RTX 50), Linux i macOS nie są przetestowane; instalowane biblioteki GPU mają kernele od Pascala do RTX 50, a Maxwell używa profilu CPU ([tabela obsługi GPU, po angielsku](docs/installation.md#1-system-requirements)).
- Tłumacz offline umie tylko angielski na turecki; inne pary językowe wymagają Codex / Claude Code CLI albo backendu API.
- Czasy słów dla języków źródłowych innych niż angielski i turecki: japoński i chiński przez `scripts/kur.ps1 -Adim hizalama-diller`, pozostałe po jednym uruchomieniu z `DUBLAJ_CEVRIMICI=1`.
- Jeszcze nie sprawdzone od początku do końca: prawdziwa instalacja XTTS-v2, RVC, bot Telegram podłączony do prawdziwej usługi i CrisperWhisper 2 Medium; Moonshine jest eksperymentalny. CrisperWhisper 2.0 Turbo (silnik 13) przetestowano na prawdziwym nagraniu na GTX 1050 Ti 4 GB (tr, en, ja; ≈ 1,4 GB VRAM).

## Klocki

Każdy etap działa samodzielnie, z wiersza poleceń albo z Pythona, a formaty plików między etapami są opisane
(mapa etapów i JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` udostępnia te same etapy jako funkcje. Instaluj tylko to, czego dany etap potrzebuje, na przykład
`pip install -e ".[stt,hizalama,cpu]"` do napisów. Pięć małych narzędzi zbudowanych z tych klocków: [examples/](examples/).

## Rodzina / powiązane projekty

| Repozytorium | Co to jest | Jak korzysta z niego to repozytorium |
|---|---|---|
| **DubWorld** (to repozytorium) | W pełni lokalny potok dubbingu wideo, każdy etap da się też używać osobno | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | Dosłowna zamiana mowy na tekst z czasami słów (CrisperWhisper 2.0 Turbo + wyrównanie CTC) | Opcjonalny silnik 13: `scripts/kur.ps1 -Adim crisper` instaluje model przez tamto repozytorium na przypiętym commicie (wagi **niekomercyjne**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Projektowanie głosu i czytanie z VoxCPM2, 8 języków, gotowe głosy | Opcjonalny silnik głosu `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` instaluje go na przypiętym commicie; to repozytorium woła go przez cienki adapter |

Każde siostrzane repozytorium ma własną licencję, instalację i zgłoszenia; dzięki przypiętemu commitowi całość da się odtworzyć z tym samym wynikiem.

## Odpowiedzialne używanie

> **Informacja prawna.** Pełną odpowiedzialność za treści, które przetwarzasz i publikujesz za pomocą tego programu, oraz za
> przestrzeganie prawa w Twoim kraju i regulaminów stron i usług, z których korzystasz, ponosisz Ty. Program jest udostępniany
> „tak jak jest”, bez żadnych gwarancji (Apache-2.0). Pełny tekst: [ETHICS.md](ETHICS.md).

- **Prawa i zgoda.** Przetwarzaj tylko treści, które są Twoje albo które masz prawo przetłumaczyć i ponownie zdubbingować,
  i poproś o zgodę osoby, które da się w nich rozpoznać.
- **Głosy.** Żadnego podszywania się. Głos referencyjny może być tylko Twój albo osoby, która wyraźnie się na to zgodziła.
- **Oznaczaj.** Wynik ma znacznik metadanych `AI-dubbed`; zostaw go i powiedz widzom w widoczny sposób,
  że dubbing powstał z pomocą AI (art. 50 AI Act UE; licencja Supertonic).
- **Pobieranie.** Opcjonalne dodatki `youtube` (yt-dlp) i `galeri` (gallery-dl) są tylko do treści, które są Twoje albo które wolno Ci pobrać; obowiązują regulamin strony i
  Twoje lokalne prawo.
- **Silniki niekomercyjne.** CrisperWhisper 2.0 i XTTS-v2 są tylko do użytku niekomercyjnego (domyślnie wyłączone). Przed płatnym zleceniem lub pracą dla klienta
  sprawdź kolumnę **Commercial?** w [THIRD_PARTY.md](THIRD_PARTY.md).
  Modele czasu słów dla nagrań źródłowych fr / de / es / it (CC BY-NC 4.0) też są niekomercyjne i przy pierwszym użyciu proszą o zgodę.

## Pomoc i wsparcie

Pytania, pomysły i Twoje wyniki: [forum dyskusji](https://github.com/alexturkey/dubworld/discussions). Problem z instalacją: [zgłoś problem z instalacją](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); błędy: [zgłoś błąd](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(podaj system, GPU, uruchomione polecenie i ostatnie linie wyniku). Sprawy bezpieczeństwa: zobacz SECURITY.md, nie pisz o nich w publicznym zgłoszeniu.

## Licencja i podziękowania

Kod: Apache-2.0 (LICENSE). Składniki zewnętrzne i ich licencje: THIRD_PARTY.md. Odpowiedzialne używanie: ETHICS.md.
Prywatność (co zostaje na Twoim komputerze, co dostaje backend w chmurze): PRIVACY.md. Zgłaszanie luk: SECURITY.md. Zmiany: CHANGELOG.md.

<!-- i18n-source: README.md sha256:2750a34df58c -->
