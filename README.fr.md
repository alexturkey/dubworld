# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · Français

> DubWorld double une vidéo dans une autre langue sur votre propre ordinateur : transcription avec horodatage des mots, traduction, voix de synthèse calée sur le minutage d'origine, sous-titres et nouvelle vidéo. Turc par défaut ; autres langues selon le moteur de voix ([docs/diller.md](docs/diller.md)).

## Laissez votre assistant IA l'installer

Aucune connaissance en programmation n'est nécessaire. Ouvrez un assistant IA capable d'exécuter des commandes sur
votre ordinateur (Claude Code, Codex, Gemini CLI ou équivalent) et collez cette seule phrase :

```text
Installe sur cet ordinateur le programme de doublage vidéo de https://github.com/alexturkey/DubWorld. Suis pas à pas le fichier AGENTS.md de ce dépôt, détecte toi-même mon matériel et ne me pose pas de questions techniques. Quand `dubla kontrol` affiche READY et que le doublage d'exemple fonctionne, ouvre-moi la fenêtre du programme.
```

L'assistant vérifie votre ordinateur, choisit lui-même l'installation avec carte graphique (GPU) ou processeur seul
(CPU) et vous pose une seule question : acceptez-vous les conditions d'utilisation de la voix. Ensuite, la fenêtre du
programme s'ouvre. Premiers pas, explications simples et problèmes fréquents (en anglais) :
**[docs/getting-started.md](docs/getting-started.md)**.

**Résumé des licences :** code Apache-2.0. Modèles par défaut : voix Supertonic 3 sous OpenRAIL-M (restrictions d'usage, acceptées une fois) ; Opus-MT et le modèle d'horodatage turc sous CC BY 4.0 (attribution, NOTICE) ; build FFmpeg GPL-3.0 (programme séparé). Non commerciaux uniquement et désactivés par défaut : CrisperWhisper 2.0, XTTS-v2, modèles d'horodatage WhisperX pour fr / de / es / it. Ce dépôt ne contient aucun poids de modèle ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Installation rapide

Windows 10/11 x64 ; Python, CUDA et ffmpeg ne sont pas nécessaires au préalable. Double-cliquez sur **`kur.cmd`** (ou
lancez `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`) ; le profil GPU ou CPU est choisi
automatiquement (`-Cpu` force le CPU). Double-cliquez ensuite sur `arayuz.cmd` pour ouvrir l'application.
Tout s'installe dans le dossier du dépôt (`.venv`, `runtime_assets/`) ; chaque téléchargement est figé en version et
vérifié par sha256. Disque : ≈ 22 Go avec le profil GPU, ≈ 13 Go en CPU seul. Vérification : `.venv\Scripts\dubla.exe kontrol`.

Prérequis, ordre des étapes, carte des environnements Python, moteurs optionnels, utilisation hors ligne, mise à jour,
désinstallation et erreurs fréquentes (en anglais) : **[docs/installation.md](docs/installation.md)**. Linux et macOS
ne sont pas encore testés.

## Utilisation

Application de bureau : double-cliquez sur `arayuz.cmd` (application web locale : `web.cmd`, 127.0.0.1 uniquement). En ligne de commande :

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Les résultats vont dans `cikti/<video>_<time>/` : `dubbed_tr.mp4` (étiqueté `AI-dubbed`), les sous-titres source `transcript_<lang>.srt` et les fichiers JSON de la tâche ; la dernière ligne `dubbed_video:` affiche le chemin. Tous les réglages : [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Fonctionnement

1. **Audio :** FFmpeg extrait le son ; Demucs optionnel (MIT) sépare la voix du fond.
2. **Parole en texte :** faster-whisper large-v3-turbo (MIT) plus horodatage des mots par wav2vec2 CTC (anglais MIT, turc CC BY 4.0) ; en option CrisperWhisper 2.0 (non commercial) et d'autres moteurs.
3. **Locuteurs :** 3D-Speaker CAM++ (Apache-2.0) et un classifieur de genre (Apache-2.0) choisissent une voix de synthèse par locuteur.
4. **Traduction :** Codex CLI ou Claude Code CLI s'ils sont installés et connectés, sinon Opus-MT local anglais → turc (CC BY 4.0) ; backends API optionnels.
5. **Voix et minutage :** Supertonic 3 (OpenRAIL-M) par défaut, VoxCPM2 (Apache-2.0) ou XTTS-v2 (non commercial) en option ; chaque phrase est calée sur la durée du segment d'origine.
6. **Vidéo :** FFmpeg écrit le nouveau son, les sous-titres SRT / VTT / ASS et l'étiquette `AI-dubbed`.

## Mesures

Machine de référence : GPU Pascal 4 Go, Windows 10 ; méthode et toutes les lignes dans [docs/olcumler.md](docs/olcumler.md).

| Quoi | Profil CPU | Profil GPU |
|---|---|---|
| Première installation, étapes par défaut | ≈ 38 min | ≈ 13,5 min (paquets) |
| Disque après installation | ≈ 13 Go | ≈ 22 Go |
| Doublage de l'exemple de 9 s, traduction hors ligne | 528 s | 376 s |
| Extrait anglais de 30 s, Demucs, traduction Claude Code | – | 744 s |

## Limites

- Sans CrisperWhisper (moteur optionnel 13), faster-whisper peut sauter de la parole ou inventer du texte en chinois et en japonais (constaté : les ≈ 10 premières secondes d'un extrait chinois sautées ; des cris transformés en une longue ligne "ああ…").
- La CI ne teste que le CPU ; le chemin GPU a été lancé à la main sur une carte Pascal de 4 Go. Les cartes récentes (RTX 50), Linux et macOS n'ont pas été essayés.
- Le traducteur hors ligne ne fait que l'anglais vers le turc ; les autres paires demandent la CLI Codex / Claude Code ou un backend API.
- Horodatage des mots pour les langues source autres que l'anglais et le turc : japonais et chinois avec `scripts/kur.ps1 -Adim hizalama-diller`, les autres après une exécution avec `DUBLAJ_CEVRIMICI=1`.
- Non testé de bout en bout : installation réelle de XTTS-v2, RVC, le bot Telegram sur le vrai service, moteurs CrisperWhisper ; Moonshine est expérimental.

## Briques de base

Chaque étape fonctionne seule, en ligne de commande ou depuis Python, avec des formats de fichiers documentés entre les
étapes (carte des étapes et schémas JSON : [docs/mimari.md](docs/mimari.md)) :

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` fournit les mêmes étapes sous forme de fonctions. N'installez que ce dont une étape a
besoin, par ex. `pip install -e ".[stt,hizalama,cpu]"` pour les sous-titres. Cinq petits outils construits avec ces
briques : [examples/](examples/).

## Projets liés

| Dépôt | Ce que c'est | Comment ce dépôt l'utilise |
|---|---|---|
| **DubWorld** (ce dépôt) | chaîne locale de doublage vidéo de bout en bout ; chaque étape utilisable seule | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | transcription verbatim avec horodatage des mots (CrisperWhisper 2.0 Turbo + alignement CTC) | moteur optionnel 13 : `scripts/kur.ps1 -Adim crisper` installe son modèle via ce dépôt à un commit figé (poids **non commerciaux uniquement**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | conception de voix et lecture avec VoxCPM2, 8 langues, voix prêtes | moteur TTS optionnel `voxcpm2` : `scripts/kur.ps1 -Adim voxcpm2` l'installe à un commit figé ; ce dépôt l'appelle via un adaptateur léger |

Chaque dépôt frère garde sa propre licence, son installation et ses tickets ; les commits figés rendent la combinaison reproductible.

## Utilisation responsable

> **Avertissement juridique.** Vous êtes seul responsable des contenus que vous traitez et publiez avec ce logiciel, et
> du respect des lois de votre juridiction ainsi que des conditions des sites et services que vous utilisez. Le logiciel
> est fourni « en l'état », sans garantie (Apache-2.0). Texte complet et version anglaise faisant foi : [ETHICS.md](ETHICS.md).

- **Droits et consentement.** Ne traitez que des contenus qui vous appartiennent ou que vous avez le droit de traduire
  et de redoubler, et obtenez le consentement des personnes identifiables qui y figurent.
- **Voix.** Aucune usurpation. Une voix de référence ne peut être que la vôtre ou celle d'une personne ayant donné son
  consentement explicite.
- **Signalez-le.** Les sorties portent une étiquette de métadonnées `AI-dubbed` ; conservez-la et indiquez aussi
  clairement à votre public qu'il s'agit d'un doublage par IA (règlement européen sur l'IA, art. 50 ; licence Supertonic).
- **Téléchargement.** Les extras optionnels `youtube` (yt-dlp) et `galeri` (gallery-dl) sont destinés aux contenus qui
  vous appartiennent ou que vous pouvez télécharger ; les conditions du site et votre droit local s'appliquent.
- **Moteurs non commerciaux.** CrisperWhisper 2.0 et XTTS-v2 sont réservés à un usage non commercial (désactivés par
  défaut). Consultez la colonne **Commercial?** de [THIRD_PARTY.md](THIRD_PARTY.md) avant tout travail rémunéré ou pour un client.

## Licence et remerciements

Code : Apache-2.0 (LICENSE). Composants tiers et leurs licences : THIRD_PARTY.md. Utilisation responsable : ETHICS.md.
Confidentialité (ce qui reste en local, ce qu'un service cloud reçoit) : PRIVACY.md. Signalements de sécurité : SECURITY.md. Changements : CHANGELOG.md.

---

> This translation may lag; English is authoritative. Cette traduction peut être en retard ; la version anglaise fait
> foi. Source : README.md (marque de synchronisation ci-dessous). Traduction automatique (Claude) ; les PR de correction sont bienvenues.

<!-- i18n-source: README.md sha256:64e0ac274650 -->
