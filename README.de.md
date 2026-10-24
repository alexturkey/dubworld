# Türkçe video dublaj hattı

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · Deutsch · [Français](README.fr.md)

> __TEK_CUMLE__ (was es tut, in einem Satz)

## Lass deinen KI-Assistenten die Installation übernehmen

Programmierkenntnisse sind nicht nötig. Öffne einen KI-Assistenten, der auf deinem Computer Befehle ausführen kann
(Claude Code, Codex, Gemini CLI o. ä.), und füge diesen einen Satz ein:

```text
Installiere das Video-Synchronisationsprogramm von __REPO_URL__ auf diesem Computer. Folge Schritt für Schritt der Datei AGENTS.md in diesem Repository, erkenne meine Hardware selbst und stelle mir keine technischen Fragen. Wenn `dubla kontrol` READY meldet und die Beispiel-Synchronisation funktioniert, öffne mir das Programmfenster.
```

Der Assistent prüft deinen Computer, wählt selbst die Einrichtung mit Grafikkarte (GPU) oder nur mit Prozessor (CPU)
und stellt dir genau eine Frage: ob du die Nutzungsbedingungen der Stimme akzeptierst. Danach öffnet sich das
Programmfenster. Erste Schritte, einfache Erklärungen und häufige Probleme (auf Englisch):
**[docs/getting-started.md](docs/getting-started.md)**.

**Lizenzübersicht:** Code Apache-2.0. __LISANS_KUTUSU__ (Modell-/Datenlizenzen, die vom Code abweichen; „keine“, wenn alles Apache-kompatibel ist)

## Schnellinstallation

Windows 10/11 x64; Python, CUDA oder ffmpeg müssen vorher nicht installiert sein. Doppelklick auf **`kur.cmd`** (oder
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1` ausführen); das GPU- oder CPU-Profil wird
automatisch gewählt (`-Cpu` erzwingt CPU). Danach `arayuz.cmd` doppelklicken, um die Anwendung zu öffnen.
Alles landet im Repository-Ordner (`.venv`, `runtime_assets/`); jeder Download ist versionsfixiert und per sha256
geprüft. Speicherplatz: ≈ 22 GB mit GPU-Profil, ≈ 13 GB nur CPU. Prüfen mit `.venv\Scripts\dubla.exe kontrol`.

Voraussetzungen, Reihenfolge der Schritte, Übersicht der Python-Umgebungen, optionale Engines, Offline-Nutzung,
Aktualisierung, Deinstallation und häufige Fehler (auf Englisch): **[docs/installation.md](docs/installation.md)**.
Linux und macOS sind noch nicht getestet.

## Verwendung

__KULLANIM__ (ein Beispielbefehl + welche Ausgabedateien entstehen)

## Funktionsweise

__NASIL__ (Pipeline in 4–6 Punkten; jedes externe Modell mit seiner Lizenz)

## Messungen

__OLCUM_TABLOSU__ (auf der Referenzmaschine gemessen, Methode in docs/olcumler.md; niemals Zahlen von anderswo übernehmen)

## Grenzen

__SINIRLAR__ (was nicht gemessen wurde, was experimentell ist, welche Hardware nicht getestet wurde)

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
| **turkce-video-dublaj-hatti** (dieses Repository) | lokale Video-Synchronisationspipeline von Anfang bis Ende; jede Stufe einzeln nutzbar | - |
| [crisperwhisper-turkce-kelime-zamani](__STT_REPO_URL__) | wortgetreue Spracherkennung mit Wort-Zeitstempeln (CrisperWhisper 2.0 Turbo + CTC-Ausrichtung) | optionale Engine 13: `scripts/kur.ps1 -Adim crisper` installiert ihr Modell über dieses Repository auf einem festen Commit (Gewichte **nur nicht-kommerziell**) |
| [voxcpm2-turkce-ses-tasarimi](__TTS_REPO_URL__) | Stimmdesign und Vorlesen mit VoxCPM2, 8 Sprachen, fertige Stimmen | optionale TTS-Engine `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` installiert sie auf einem festen Commit; dieses Repository ruft sie über einen schlanken Adapter auf |

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

## Lizenz und Danksagung

Code: Apache-2.0 (LICENSE). Drittkomponenten und ihre Lizenzen: THIRD_PARTY.md. Verantwortungsvolle Nutzung: ETHICS.md.
Datenschutz (was lokal bleibt, was ein Cloud-Dienst erhält): PRIVACY.md. Sicherheitsmeldungen: SECURITY.md. Änderungen: CHANGELOG.md.

---

> This translation may lag; English is authoritative. Diese Übersetzung kann hinterherhinken; maßgeblich ist die
> englische Fassung. Quelle: README.md (Synchronisationsmarke unten). Maschinell übersetzt (Claude); Korrektur-PRs willkommen.

<!-- i18n-source: README.md sha256:bf85d79d8132 -->
