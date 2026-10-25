# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · [Português (BR)](README.pt-BR.md) · Italiano · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md)

> DubWorld doppia un video in un'altra lingua direttamente sul tuo computer, senza caricarlo su nessun servizio: trascrive il parlato con i tempi di ogni parola, lo traduce, lo fa leggere a una voce sintetica che resta a tempo con il video originale (il parlato accelera al massimo di 1,25×, il resto lo recupera l'immagine con un leggero rallentamento o accelerazione), aggiunge i sottotitoli e consegna un video nuovo. La lingua predefinita è il turco; l'italiano e le altre lingue dipendono dal motore vocale scelto ([docs/diller.md](docs/diller.md)).

## Fallo installare al tuo assistente IA

Non serve saper programmare. Apri un assistente IA che possa eseguire comandi sul tuo computer (Claude Code, Codex,
Gemini CLI o simili) e incolla questa frase:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

L'assistente misura il tuo computer (scheda video, processore, memoria, disco) e ti chiede una sola volta, a parole
semplici, che installazione vuoi: rapida, consigliata per il tuo computer o completa. Ti spiega ogni componente (cosa fa,
quanto spazio occupa, quanto tempo richiede, che licenza ha) e ti chiede se accetti le condizioni d'uso di quelli che
scegli, a partire dalla voce predefinita. Poi installa, fa un doppiaggio di prova e apre la finestra del programma.
Primi passi e problemi frequenti spiegati in modo semplice (in inglese): **[docs/getting-started.md](docs/getting-started.md)**.

**Licenze in breve:** codice Apache-2.0. Modelli predefiniti: voce Supertonic 3 con licenza OpenRAIL-M (limiti d'uso, da accettare una volta); Opus-MT e il modello turco per i tempi delle parole con CC BY 4.0 (attribuzione, NOTICE); build di FFmpeg GPL-3.0 (programma separato). Solo uso non commerciale e disattivati di default: CrisperWhisper 2.0, XTTS-v2 e i modelli WhisperX per i tempi delle parole in fr / de / es / it. In questo repository non c'è nessun peso di modello ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Installazione rapida

Windows 10/11 x64; non servono Python, CUDA o ffmpeg già installati. Fai doppio clic su **`kur.cmd`** (oppure esegui
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); sceglie da solo il profilo GPU o CPU
(`-Cpu` forza la CPU). Poi doppio clic su `arayuz.cmd` per aprire l'app.
Tutto resta dentro la cartella del repository (`.venv`, `runtime_assets/`); ogni download ha una versione fissa ed è
verificato con sha256. Spazio libero per iniziare: 22 GB con il profilo GPU, 14 GB solo CPU; spazio misurato dopo l'installazione ≈ 14,6 GB (GPU, file con hard link contati una volta; Esplora file mostra ≈ 22 GB). Verifica con `.venv\Scripts\dubla.exe kontrol`.

Requisiti, ordine dei passaggi, mappa degli ambienti Python, motori opzionali, uso offline, aggiornamento,
disinstallazione ed errori frequenti (in inglese): **[docs/installation.md](docs/installation.md)**. Linux e macOS non sono ancora stati testati da noi. Esempio: [tour di un prodotto doppiato in inglese, turco e arabo su un Mac Apple M4, solo CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Come si usa

App desktop: doppio clic su `arayuz.cmd` (app web locale: `web.cmd`, solo su 127.0.0.1). Per ora l'interfaccia dell'app è in turco. Da riga di comando:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Per doppiare in italiano usa `--ayar genel.hedef_dil=it` (la traduzione in italiano richiede Codex o Claude Code). I risultati finiscono in `cikti/<video>_<time>/`: `dubbed_tr.mp4` (con il tag `AI-dubbed`), i sottotitoli originali `transcript_<lang>.srt` e i file JSON del lavoro; l'ultima riga, `dubbed_video:`, stampa il percorso. Tutte le impostazioni (in inglese e turco): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Come funziona

1. **Audio:** FFmpeg estrae il suono; Demucs (MIT), opzionale, separa la voce dal sottofondo.
2. **Dal parlato al testo:** faster-whisper large-v3-turbo (MIT) più i tempi delle parole con wav2vec2 CTC (inglese MIT, turco CC BY 4.0); in opzione CrisperWhisper 2.0 (non commerciale) e altri motori.
3. **Speaker:** 3D-Speaker CAM++ (Apache-2.0) e un classificatore di genere (Apache-2.0) assegnano una voce sintetica a ogni speaker.
4. **Traduzione:** Codex CLI o Claude Code CLI se installati e con accesso effettuato, altrimenti Opus-MT locale dall'inglese al turco (CC BY 4.0); i backend API sono opzionali.
5. **Voce e sincronia:** Supertonic 3 (OpenRAIL-M) di default, VoxCPM2 (Apache-2.0) o XTTS-v2 (non commerciale) in opzione; ogni frase accelera al massimo di 1,25× verso la durata del segmento originale e il video viene ritemporizzato per il resto, quindi il doppiaggio può durare più dell'originale.
6. **Video:** FFmpeg scrive il nuovo audio, i sottotitoli SRT / VTT / ASS e il tag `AI-dubbed`.

## Misure

Macchina di riferimento: GPU Pascal da 4 GB, Windows 10; metodo e tutte le righe in [docs/olcumler.md](docs/olcumler.md).

| Cosa | Profilo CPU | Profilo GPU |
|---|---|---|
| Prima installazione, passaggi predefiniti, dall'inizio alla fine | ≈ 38 min | ≈ 44 min (pacchetti 13,7 min) |
| Disco dopo l'installazione | ≈ 13,2 GB (somma della cartella) | ≈ 14,6 GB (hard link contati una volta) |
| Doppiaggio di prova da 9 s, traduzione offline | 528 s | 376 s |
| Clip in inglese da 30 s, Demucs, traduzione con Claude Code | – | 744 s |

## Limiti

- Senza CrisperWhisper (motore opzionale 13), faster-whisper può saltare parti del parlato o inventare testo in cinese e giapponese (visto: i primi ≈ 10 s di una clip cinese saltati; un urlo trasformato in una lunga riga di "ああ…").
- La CI testa solo la CPU; il percorso GPU è stato eseguito a mano su una scheda Pascal da 4 GB. Schede più nuove (RTX 50), Linux e macOS non sono stati provati; le librerie GPU installate contengono kernel da Pascal a RTX 50, mentre Maxwell usa il profilo CPU ([tabella di supporto GPU, in inglese](docs/installation.md#1-system-requirements)).
- Il traduttore offline fa solo inglese → turco; le altre coppie richiedono Codex / Claude Code CLI o un backend API.
- Tempi delle parole per audio sorgente diverso da inglese e turco: giapponese e cinese con `scripts/kur.ps1 -Adim hizalama-diller`, le altre lingue dopo un'esecuzione con `DUBLAJ_CEVRIMICI=1`.
- Non ancora provati dall'inizio alla fine: installazione reale di XTTS-v2, RVC, il bot Telegram con il servizio vero e CrisperWhisper 2 Medium; Moonshine è sperimentale. CrisperWhisper 2.0 Turbo (motore 13) è testato su audio reale con una GTX 1050 Ti da 4 GB (tr, en, ja; ≈ 1,4 GB di VRAM).

## Mattoncini

Ogni fase funziona anche da sola, da riga di comando o da Python, con formati di file documentati tra una fase e l'altra
(mappa delle fasi e JSON Schema: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` offre le stesse fasi come funzioni. Installa solo ciò che serve alla fase, per esempio
`pip install -e ".[stt,hizalama,cpu]"` per i sottotitoli. Cinque piccoli strumenti costruiti con questi mattoncini: [examples/](examples/).

## Famiglia / Progetti collegati

| Repository | Cos'è | Come lo usa questo repository |
|---|---|---|
| **DubWorld** (questo repository) | pipeline completa di doppiaggio video in locale, ogni fase usabile da sola | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | trascrizione alla lettera con i tempi delle parole (CrisperWhisper 2.0 Turbo + allineamento CTC) | motore opzionale 13: `scripts/kur.ps1 -Adim crisper` ne installa il modello tramite quel repository a un commit fisso (pesi **non commerciali**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | design e lettura di voci con VoxCPM2, 8 lingue, voci pronte | motore vocale opzionale `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` lo installa a un commit fisso; questo repository lo richiama con un adattatore leggero |

Ogni repository fratello ha la sua licenza, la sua installazione e le sue issue; i commit fissi rendono la combinazione riproducibile.

## Uso responsabile

> **Avvertenza legale.** Sei l'unico responsabile dei contenuti che elabori e pubblichi con questo software e del
> rispetto delle leggi del tuo paese e dei termini dei siti e dei servizi che usi. Il software è fornito "così com'è",
> senza garanzie (Apache-2.0). Testo completo: [ETHICS.md](ETHICS.md).

- **Diritti e consenso.** Elabora solo materiale tuo o che hai il permesso di tradurre e ridoppiare, e chiedi il
  consenso delle persone riconoscibili.
- **Voci.** Niente imitazioni di persone. Una voce di riferimento può essere solo la tua o quella di chi ha dato un consenso esplicito.
- **Dichiaralo.** I file prodotti hanno il tag nei metadati `AI-dubbed`; lascialo e indica anche in modo visibile al
  tuo pubblico che il doppiaggio è fatto con l'IA (AI Act UE, art. 50; licenza Supertonic).
- **Download.** Gli extra opzionali `youtube` (yt-dlp) e `galeri` (gallery-dl) servono per contenuti tuoi o che puoi scaricare; valgono i termini del sito e
  la legge del tuo paese.
- **Motori non commerciali.** CrisperWhisper 2.0 e XTTS-v2 sono solo per uso non commerciale (disattivati di default). Guarda
  la colonna **Commercial?** di [THIRD_PARTY.md](THIRD_PARTY.md) prima di qualsiasi lavoro pagato o per clienti.
  Anche i modelli per i tempi delle parole su audio in fr / de / es / it (CC BY-NC 4.0) sono non commerciali e chiedono il consenso al primo uso.

## Aiuto e supporto

Domande, idee e risultati: [Discussioni](https://github.com/alexturkey/dubworld/discussions). Problemi di installazione: [apri una segnalazione di installazione](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); bug: [segnala un bug](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(indica sistema operativo, GPU, il comando e le ultime righe dell'output). Problemi di sicurezza: SECURITY.md, mai nelle issue pubbliche.

## Licenza e riconoscimenti

Codice: Apache-2.0 (LICENSE). Componenti di terze parti e relative licenze: THIRD_PARTY.md. Uso responsabile: ETHICS.md.
Privacy (cosa resta sul tuo computer e cosa riceve un backend cloud): PRIVACY.md. Segnalazioni di sicurezza: SECURITY.md. Modifiche: CHANGELOG.md.

<!-- i18n-source: README.md sha256:2e512198d98b -->
