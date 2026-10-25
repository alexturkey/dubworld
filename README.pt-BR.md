# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [العربية](README.ar.md) · Português (BR) · [Italiano](README.it.md) · [한국어](README.ko.md) · [हिन्दी](README.hi.md) · [Bahasa Indonesia](README.id.md) · [Tiếng Việt](README.vi.md) · [Polski](README.pl.md) · [Nederlands](README.nl.md) · [Українська](README.uk.md) · [فارسی](README.fa.md) · [Ελληνικά](README.el.md) · [Čeština](README.cs.md) · [Română](README.ro.md) · [Magyar](README.hu.md) · [Svenska](README.sv.md)

> O DubWorld dubla um vídeo para outro idioma no seu próprio computador, sem mandar nada para a nuvem: transcreve a fala com o tempo de cada palavra, traduz, gera uma voz sintética que acompanha o vídeo original (a fala acelera no máximo 1,25× e a imagem é reajustada para cobrir o resto), cria as legendas e entrega um vídeo novo. O padrão é turco; português e outros idiomas dependem do motor de voz escolhido ([docs/diller.md](docs/diller.md)).

## Deixe seu assistente de IA instalar para você

Você não precisa saber programar. Abra um assistente de IA que consiga rodar comandos no seu computador (Claude Code,
Codex, Gemini CLI ou parecido) e cole esta frase:

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

O assistente analisa o seu computador (placa de vídeo, processador, memória, disco) e pergunta uma única vez, em
linguagem simples, que tipo de instalação você quer: rápida, recomendada para a sua máquina ou completa. Ele explica
cada parte (o que faz, quanto ocupa, quanto demora e qual a licença) e pergunta se você aceita os termos de uso das
partes escolhidas, começando pela voz padrão. Depois instala, faz uma dublagem de teste e abre a janela do programa.
Primeiros passos e problemas comuns, em linguagem simples (em inglês): **[docs/getting-started.md](docs/getting-started.md)**.

**Licenças em resumo:** código Apache-2.0. Modelos padrão: voz Supertonic 3 sob OpenRAIL-M (restrições de uso, aceitas uma vez); Opus-MT e o modelo turco de tempo por palavra sob CC BY 4.0 (atribuição, NOTICE); build do FFmpeg GPL-3.0 (programa separado). Só para uso não comercial e desligados por padrão: CrisperWhisper 2.0, XTTS-v2 e os modelos de tempo por palavra do WhisperX para fr / de / es / it. Nenhum peso de modelo fica neste repositório ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Instalação rápida

Windows 10/11 x64; não precisa instalar Python, CUDA nem ffmpeg antes. Dê dois cliques em **`kur.cmd`** (ou rode
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); ele escolhe sozinho o perfil GPU ou CPU
(`-Cpu` força CPU). Depois dê dois cliques em `arayuz.cmd` para abrir o app.
Tudo fica dentro da pasta do repositório (`.venv`, `runtime_assets/`); cada download tem versão fixa e é conferido
por sha256. Espaço livre para começar: 22 GB com o perfil GPU, 14 GB só com CPU; uso medido depois da instalação ≈ 14,6 GB (GPU, arquivos com hard link contados uma vez; o Explorador de Arquivos mostra ≈ 22 GB). Confira com `.venv\Scripts\dubla.exe kontrol`.

Requisitos, ordem dos passos, mapa dos ambientes Python, motores opcionais, uso offline, atualização, desinstalação e
erros comuns (em inglês): **[docs/installation.md](docs/installation.md)**. Linux e macOS ainda não foram testados por nós. Exemplo: [tour de produto narrado em inglês, turco e árabe num Mac Apple M4, só com CPU](https://x.com/MihenkAIdotcom/status/2114345171571925363).

## Como usar

App de desktop: dois cliques em `arayuz.cmd` (app web local: `web.cmd`, só em 127.0.0.1). Por enquanto a interface do app está em turco. Pela linha de comando:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Para dublar em português, use `--ayar genel.hedef_dil=pt` (a tradução para português precisa do Codex ou do Claude Code). Os resultados vão para `cikti/<video>_<time>/`: `dubbed_tr.mp4` (marcado como `AI-dubbed`), a legenda original `transcript_<lang>.srt` e os arquivos JSON do trabalho; a última linha, `dubbed_video:`, mostra o caminho. Todas as configurações (em inglês e turco): [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Como funciona

1. **Áudio:** o FFmpeg extrai o som; o Demucs (MIT), opcional, separa a fala do fundo.
2. **Fala para texto:** faster-whisper large-v3-turbo (MIT) com tempo por palavra via wav2vec2 CTC (inglês MIT, turco CC BY 4.0); opcionalmente CrisperWhisper 2.0 (não comercial) e outros motores.
3. **Falantes:** o 3D-Speaker CAM++ (Apache-2.0) e um classificador de gênero (Apache-2.0) escolhem uma voz sintética para cada falante.
4. **Tradução:** Codex CLI ou Claude Code CLI, se estiverem instalados e logados; senão, Opus-MT local de inglês para turco (CC BY 4.0); backends de API são opcionais.
5. **Voz e sincronia:** Supertonic 3 (OpenRAIL-M) por padrão, VoxCPM2 (Apache-2.0) ou XTTS-v2 (não comercial) como opção; cada frase acelera no máximo 1,25× em direção ao tempo do trecho original e o vídeo é reajustado para o resto, então a dublagem pode ficar mais longa que o original.
6. **Vídeo:** o FFmpeg grava o áudio novo, as legendas SRT / VTT / ASS e a marca `AI-dubbed`.

## Medições

Máquina de referência: GPU Pascal de 4 GB, Windows 10; método e todas as linhas em [docs/olcumler.md](docs/olcumler.md).

| O quê | Perfil CPU | Perfil GPU |
|---|---|---|
| Primeira instalação, passos padrão, do início ao fim | ≈ 38 min | ≈ 44 min (pacotes 13,7 min) |
| Disco depois da instalação | ≈ 13,2 GB (soma da pasta) | ≈ 14,6 GB (hard links contados uma vez) |
| Dublagem de teste de 9 s, tradução offline | 528 s | 376 s |
| Trecho em inglês de 30 s, Demucs, tradução com Claude Code | – | 744 s |

## Limitações

- Sem o CrisperWhisper (motor opcional 13), o faster-whisper pode pular falas ou inventar texto em chinês e japonês (já vimos: os primeiros ≈ 10 s de um trecho em chinês pulados; um grito virou uma linha comprida de "ああ…").
- O CI testa só a CPU; o caminho GPU foi rodado à mão numa placa Pascal de 4 GB. Placas mais novas (RTX 50), Linux e macOS não foram testados; as bibliotecas de GPU instaladas trazem kernels do Pascal até a RTX 50, e a Maxwell usa o perfil CPU ([tabela de suporte de GPU, em inglês](docs/installation.md#1-system-requirements)).
- O tradutor offline só faz inglês para turco; outros pares precisam do Codex / Claude Code CLI ou de um backend de API.
- Tempo por palavra para áudio de origem que não seja inglês nem turco: japonês e chinês com `scripts/kur.ps1 -Adim hizalama-diller`; os outros depois de uma execução com `DUBLAJ_CEVRIMICI=1`.
- Ainda não testados de ponta a ponta: instalação real do XTTS-v2, RVC, o bot do Telegram com o serviço real e o CrisperWhisper 2 Medium; o Moonshine é experimental. O CrisperWhisper 2.0 Turbo (motor 13) foi testado com áudio real numa GTX 1050 Ti de 4 GB (tr, en, ja; ≈ 1,4 GB de VRAM).

## Blocos de montar

Cada etapa funciona sozinha, pela linha de comando ou pelo Python, com formatos de arquivo documentados entre elas
(mapa das etapas e JSON Schemas: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` oferece as mesmas etapas como funções. Instale só o que a etapa precisa, por exemplo
`pip install -e ".[stt,hizalama,cpu]"` para gerar legendas. Cinco ferramentas pequenas feitas com esses blocos: [examples/](examples/).

## Família / Projetos relacionados

| Repositório | O que é | Como este repositório usa |
|---|---|---|
| **DubWorld** (este repositório) | pipeline completo de dublagem de vídeo local, cada etapa usável sozinha | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | transcrição literal com tempo por palavra (CrisperWhisper 2.0 Turbo + alinhamento CTC) | motor opcional 13: `scripts/kur.ps1 -Adim crisper` instala o modelo por esse repositório num commit fixo (pesos **não comerciais**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | design e leitura de vozes com VoxCPM2, 8 idiomas, vozes prontas | motor de voz opcional `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` instala num commit fixo; este repositório chama por um adaptador fino |

Cada repositório irmão tem sua própria licença, instalação e issues; os commits fixos tornam a combinação reproduzível.

## Uso responsável

> **Aviso legal.** Você é o único responsável pelo conteúdo que processa e publica com este software e por cumprir
> as leis do seu país e os termos dos sites e serviços que usa. O software é fornecido "como está", sem garantia
> (Apache-2.0). Texto completo: [ETHICS.md](ETHICS.md).

- **Direitos e consentimento.** Processe só material que é seu ou que você tem permissão para traduzir e redublar, e
  peça o consentimento das pessoas identificáveis nele.
- **Vozes.** Nada de imitar pessoas. Uma voz de referência só pode ser a sua ou a de alguém que deu consentimento explícito.
- **Sinalize.** As saídas levam a marca de metadados `AI-dubbed`; mantenha essa marca e avise também, de forma visível, o
  seu público de que a dublagem foi feita por IA (Lei de IA da UE, art. 50; licença do Supertonic).
- **Downloads.** Os extras opcionais `youtube` (yt-dlp) e `galeri` (gallery-dl) são para conteúdo que é seu ou que você pode baixar; valem os termos do site e
  a lei do seu país.
- **Motores não comerciais.** CrisperWhisper 2.0 e XTTS-v2 são só para uso não comercial (desligados por padrão). Veja
  a coluna **Commercial?** do [THIRD_PARTY.md](THIRD_PARTY.md) antes de qualquer trabalho pago ou para cliente.
  Os modelos de tempo por palavra para áudio em fr / de / es / it (CC BY-NC 4.0) também são não comerciais e pedem consentimento no primeiro uso.

## Ajuda e suporte

Dúvidas, ideias e resultados: [Discussões](https://github.com/alexturkey/dubworld/discussions). Problemas de instalação: [abrir issue de instalação](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); bugs: [reportar bug](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(informe o sistema, a GPU, o comando e as últimas linhas da saída). Falhas de segurança: SECURITY.md, nunca em issues públicas.

## Licença e créditos

Código: Apache-2.0 (LICENSE). Componentes de terceiros e suas licenças: THIRD_PARTY.md. Uso responsável: ETHICS.md.
Privacidade (o que fica no seu computador e o que um backend na nuvem recebe): PRIVACY.md. Relatos de segurança: SECURITY.md. Mudanças: CHANGELOG.md.

<!-- i18n-source: README.md sha256:48bbf9594411 -->
