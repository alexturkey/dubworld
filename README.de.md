# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · Deutsch · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [עברית](README.he.md) · [ไทย](README.th.md) · [বাংলা](README.bn.md) · [اردو](README.ur.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md) · [Azərbaycanca](README.az.md) · [Bahasa Melayu](README.ms.md)

> DubWorld synchronisiert ein Video auf dem eigenen Computer in eine andere Sprache: Spracherkennung mit Wort-Zeitstempeln, Übersetzung, synthetische Stimme im Takt des Originalvideos (Sprache höchstens 1,25× beschleunigt, den Rest gleicht das Bild aus), Untertitel und ein neues Video. Standard ist Türkisch; weitere Sprachen je nach Sprachausgabe-Engine ([docs/diller.md](docs/diller.md)).

## Lass deinen KI-Assistenten die Installation übernehmen

Programmierkenntnisse sind nicht nötig. Öffne einen KI-Assistenten, der auf deinem Computer Befehle ausführen kann
(Claude Code, Codex, Gemini CLI o. ä.), und füge diesen einen Satz ein:

```text
Installiere das Video-Synchronisationsprogramm von https://github.com/alexturkey/DubWorld auf diesem Computer. Folge Schritt für Schritt der Datei AGENTS.md in diesem Repository, erkenne meine Hardware selbst und stelle mir keine technischen Fragen. Wenn `dubla kontrol` READY meldet und die Beispiel-Synchronisation funktioniert, öffne mir das Programmfenster.
```

Der Assistent misst deinen Computer (Grafikkarte, Prozessor, Arbeitsspeicher, Festplatte) und fragt dich einmal in
einfachen Worten, welche Einrichtung du willst: schnell, für deinen Computer empfohlen oder vollständig. Er erklärt
jeden Teil (was er tut, wie viel Speicherplatz und Zeit er braucht, seine Lizenz) und fragt, ob du die
Nutzungsbedingungen der gewählten Teile akzeptierst, zuerst die der Standardstimme. Danach installiert er, macht eine
Beispielsynchronisation und öffnet das Programmfenster. Erste Schritte, einfache Erklärungen und häufige Probleme (auf
Englisch): **[docs/getting-started.md](docs/getting-started.md)**.

**Lizenzübersicht:** Code Apache-2.0. Standardmodelle: Supertonic-3-Stimme unter OpenRAIL-M (Nutzungsbeschränkungen, einmalige Zustimmung); Opus-MT und das türkische Wort-Zeitmodell unter CC BY 4.0 (Namensnennung, NOTICE); FFmpeg-Build GPL-3.0 (separates Programm). Nur nicht kommerziell und standardmäßig aus: CrisperWhisper 2.0, XTTS-v2, WhisperX-Wort-Zeitmodelle für fr / de / es / it. Dieses Repository enthält keine Modellgewichte ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Schnellinstallation

Windows 10/11 x64; Python, CUDA oder ffmpeg müssen vorher nicht installiert sein. Doppelklick auf **`kur.cmd`** (oder
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` ausführen); das GPU- oder CPU-Profil wird
automatisch gewählt (`-Cpu` erzwingt CPU). Danach `arayuz.cmd` doppelklicken, um die Anwendung zu öffnen.
Alles landet im Repository-Ordner (`.venv`, `runtime_assets/`); jeder Download ist versionsfixiert und per sha256
geprüft. Freier Speicherplatz zum Start: 22 GB mit GPU-Profil, 14 GB nur CPU; gemessene Belegung nach der Installation ≈ 14,6 GB (GPU, Dateien mit festen Links einmal gezählt; der Explorer zeigt ≈ 22 GB). Prüfen mit `.venv\Scripts\dubla.exe kontrol`.

Voraussetzungen, Reihenfolge der Schritte, Übersicht der Python-Umgebungen, optionale Engines, Offline-Nutzung,
Aktualisierung, Deinstallation und häufige Fehler (auf Englisch): **[docs/installation.md](docs/installation.md)**.
Linux und macOS sind noch nicht getestet. Beispiel: [Produkttour auf Englisch, Türkisch und Arabisch, vertont auf einem Apple M4 Mac, nur CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Verwendung

Desktop-App: Doppelklick auf `arayuz.cmd` (lokale Web-App: `web.cmd`, nur 127.0.0.1). Die Oberfläche der App ist vorerst auf Türkisch. Über die Kommandozeile:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Ergebnisse landen in `cikti/<video>_<time>/`: `dubbed_tr.mp4` (mit `AI-dubbed`-Kennzeichnung), die Quell-Untertitel `transcript_<lang>.srt` und die JSON-Dateien des Auftrags; die letzte Zeile `dubbed_video:` nennt den Pfad. Alle Einstellungen: [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Funktionsweise

1. **Audio:** FFmpeg extrahiert den Ton; optional trennt Demucs (MIT) Sprache vom Hintergrund.
2. **Sprache zu Text:** faster-whisper large-v3-turbo (MIT) plus Wort-Zeitstempel mit wav2vec2 CTC (Englisch MIT, Türkisch CC BY 4.0); optional CrisperWhisper 2.0 (nicht kommerziell) und weitere Engines.
3. **Sprecher:** 3D-Speaker CAM++ (Apache-2.0) und ein Geschlechtsklassifikator (Apache-2.0) wählen pro Sprecher eine synthetische Stimme.
4. **Übersetzung:** Codex CLI oder Claude Code CLI, wenn installiert und angemeldet, sonst lokales Opus-MT Englisch→Türkisch (CC BY 4.0); API-Backends optional.
5. **Stimme und Timing:** standardmäßig Supertonic 3 (OpenRAIL-M), optional VoxCPM2 (Apache-2.0) oder XTTS-v2 (nicht kommerziell); jede Zeile wird höchstens 1,25× in Richtung der Dauer des Originalsegments beschleunigt, den Rest gleicht das Video aus, daher kann die Synchronisation länger sein als die Quelle.
6. **Video:** FFmpeg schreibt den neuen Ton, SRT-/VTT-/ASS-Untertitel und die `AI-dubbed`-Kennzeichnung.

## Messungen

Referenzrechner: Pascal-GPU mit 4 GB, Windows 10; Methode und alle Zeilen in [docs/olcumler.md](docs/olcumler.md).

| Was | CPU-Profil | GPU-Profil |
|---|---|---|
| Erstinstallation, Standardschritte, komplett | ≈ 38 min | ≈ 44 min (Pakete 13,7 min) |
| Speicherplatz nach der Installation | ≈ 13,2 GB (Ordnersumme) | ≈ 14,6 GB (feste Links einmal gezählt) |
| Synchronisation des 9-s-Beispiels, Offline-Übersetzung | 528 s | 376 s |
| 30-s-Clip auf Englisch, Demucs, Übersetzung mit Claude Code | – | 744 s |

## Grenzen

- Ohne CrisperWhisper (optionale Engine 13) kann faster-whisper auf Chinesisch und Japanisch Sprache überspringen oder Text erfinden (beobachtet: die ersten ≈ 10 s eines chinesischen Clips fehlten; Geschrei wurde zu einer langen Zeile "ああ…").
- Die CI testet nur die CPU; der GPU-Pfad wurde von Hand auf einer Pascal-Karte mit 4 GB ausgeführt. Neuere Karten (RTX 50), Linux und macOS wurden nicht getestet; die installierten GPU-Bibliotheken enthalten Kernel von Pascal bis RTX 50, Maxwell nutzt das CPU-Profil ([GPU runtime matrix](docs/installation.md#1-system-requirements)).
- Der Offline-Übersetzer kann nur Englisch→Türkisch; andere Sprachpaare brauchen die Codex / Claude Code CLI oder ein API-Backend.
- Wort-Zeitstempel für andere Quellsprachen als Englisch und Türkisch: Japanisch und Chinesisch mit `scripts/kur.ps1 -Adim hizalama-diller`, andere nach einem Lauf mit `DUBLAJ_CEVRIMICI=1`.
- Nicht durchgängig getestet: echte Installation von XTTS-v2, RVC, der Telegram-Bot mit dem echten Dienst, CrisperWhisper 2 Medium; Moonshine ist experimentell. CrisperWhisper 2.0 Turbo (Engine 13) ist mit echtem Audio auf einer GTX 1050 Ti 4 GB getestet (tr, en, ja; ≈ 1,4 GB VRAM).

## Bausteine

Jede Stufe läuft für sich allein, über die Kommandozeile oder aus Python, mit dokumentierten Dateiformaten dazwischen
(Stufenübersicht und JSON-Schemas: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` stellt dieselben Stufen als Funktionen bereit. Installiere nur, was eine Stufe braucht,
z. B. `pip install -e ".[stt,hizalama,cpu]"` für Untertitel. Fünf kleine Werkzeuge aus diesen Bausteinen: [examples/](examples/).

## Verwandte Projekte

| Repository | Was es ist | Wie dieses Repository es nutzt |
|---|---|---|
| **DubWorld** (dieses Repository) | lokale Video-Synchronisationspipeline von Anfang bis Ende; jede Stufe einzeln nutzbar | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | wortgetreue Spracherkennung mit Wort-Zeitstempeln (CrisperWhisper 2.0 Turbo + CTC-Ausrichtung) | optionale Engine 13: `scripts/kur.ps1 -Adim crisper` installiert ihr Modell über dieses Repository auf einem festen Commit (Gewichte **nur nicht-kommerziell**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | Stimmdesign und Vorlesen mit VoxCPM2, 8 Sprachen, fertige Stimmen | optionale TTS-Engine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installiert sie auf einem festen Commit; dieses Repository ruft sie über einen schlanken Adapter auf |

Jedes Schwester-Repository hat eigene Lizenz, Installation und Issues; feste Commits machen die Kombination reproduzierbar.

## Verantwortungsvolle Nutzung

> **Rechtlicher Hinweis.** Für die Inhalte, die du mit dieser Software verarbeitest und veröffentlichst, und für die
> Einhaltung der Gesetze deines Landes sowie der Bedingungen der genutzten Websites und Dienste bist allein du
> verantwortlich. Die Software wird „wie besehen“ ohne Gewährleistung bereitgestellt (Apache-2.0). Volltext und
> verbindliche englische Fassung: [ETHICS.md](ETHICS.md).

- **Rechte und Einwilligung.** Verarbeite nur Material, das dir gehört oder für das du eine Erlaubnis zum Übersetzen
  und Neuvertonen hast, und hole die Einwilligung erkennbarer Personen darin ein.
- **Stimmen.** Keine Identitätstäuschung. Eine Referenzstimme darf nur deine eigene sein oder eine, deren Inhaber
  ausdrücklich zugestimmt hat.
- **Kennzeichnen.** Ausgaben tragen ein Metadaten-Tag `AI-dubbed`; behalte es und weise dein Publikum zusätzlich
  sichtbar auf die KI-Synchronisation hin (EU-KI-Verordnung Art. 50; Supertonic-Lizenz).
- **Herunterladen.** Die optionalen Extras `youtube` (yt-dlp) und `galeri` (gallery-dl) sind für Inhalte gedacht, die
  dir gehören oder die du herunterladen darfst; es gelten die Bedingungen der Website und dein lokales Recht.
- **Nicht-kommerzielle Engines.** CrisperWhisper 2.0 und XTTS-v2 sind nur für nicht-kommerzielle Nutzung (standardmäßig
  aus). Prüfe vor bezahlter Arbeit oder Kundenaufträgen die Spalte **Commercial?** in [THIRD_PARTY.md](THIRD_PARTY.md).
  Die Wort-Zeitmodelle für fr / de / es / it als Ausgangssprache (CC BY-NC 4.0) sind ebenfalls nicht kommerziell und fragen bei der ersten Nutzung nach Zustimmung.

## Hilfe und Support

Fragen, Ideen und Ergebnisse: [Discussions](https://github.com/alexturkey/dubworld/discussions). Installationsprobleme: [Installations-Issue](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); Fehler: [Fehlerbericht](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(mit Betriebssystem, GPU, Befehl und letzten Ausgabezeilen). Sicherheitslücken: SECURITY.md, nicht als öffentliches Issue.

## Lizenz und Danksagung

Code: Apache-2.0 (LICENSE). Drittkomponenten und ihre Lizenzen: THIRD_PARTY.md. Verantwortungsvolle Nutzung: ETHICS.md.
Datenschutz (was lokal bleibt, was ein Cloud-Dienst erhält): PRIVACY.md. Sicherheitsmeldungen: SECURITY.md. Änderungen: CHANGELOG.md.

---

> This translation may lag; English is authoritative. Diese Übersetzung kann hinterherhinken; maßgeblich ist die
> englische Fassung. Quelle: README.md (Synchronisationsmarke unten). Maschinell übersetzt (Claude); Korrektur-PRs willkommen.

<!-- i18n-source: README.md sha256:08d5cfa0c4f9 -->
