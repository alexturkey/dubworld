# DubWorld

[English](README.md) · [Türkçe](README.tr.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · Español · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

> DubWorld dobla un vídeo a otro idioma en tu propio ordenador: transcripción con marcas de tiempo por palabra, traducción, voz sintética al ritmo del vídeo original (el habla se acelera como mucho 1,25×, el resto lo absorbe la imagen), subtítulos y un vídeo nuevo. Turco por defecto; otros idiomas según el motor de voz ([docs/diller.md](docs/diller.md)).

## Deja que tu asistente de IA lo instale

No hace falta saber programar. Abre un asistente de IA que pueda ejecutar comandos en tu ordenador (Claude Code, Codex,
Gemini CLI o similar) y pega esta única frase:

```text
Instala en este ordenador el programa de doblaje de vídeo de https://github.com/alexturkey/DubWorld. Sigue paso a paso el archivo AGENTS.md de ese repositorio, detecta tú mismo mi hardware y no me hagas preguntas técnicas. Cuando `dubla kontrol` diga READY y el doblaje de ejemplo funcione, ábreme la ventana del programa.
```

El asistente mide tu ordenador (tarjeta gráfica, procesador, memoria, disco) y te pregunta una sola vez, con palabras
sencillas, qué instalación quieres: rápida, recomendada para tu ordenador o completa. Explica cada parte (qué hace,
cuánto disco y tiempo ocupa, su licencia) y te pregunta si aceptas las condiciones de uso de las partes que elijas,
empezando por la voz por defecto. Después instala, hace un doblaje de muestra y abre la ventana del programa. Primeros
pasos, explicaciones sencillas y problemas frecuentes (en inglés):
**[docs/getting-started.md](docs/getting-started.md)**.

**Resumen de licencias:** código Apache-2.0. Modelos por defecto: voz Supertonic 3 con OpenRAIL-M (restricciones de uso, se acepta una vez); Opus-MT y el modelo de tiempo por palabra para turco con CC BY 4.0 (atribución, NOTICE); compilación de FFmpeg GPL-3.0 (programa aparte). Solo no comercial y desactivados por defecto: CrisperWhisper 2.0, XTTS-v2, modelos de tiempo por palabra de WhisperX para fr / de / es / it. Este repositorio no contiene pesos de modelos ([THIRD_PARTY.md](THIRD_PARTY.md)).

## Instalación rápida

Windows 10/11 x64; no necesitas Python, CUDA ni ffmpeg de antemano. Haz doble clic en **`kur.cmd`** (o ejecuta
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\kur.ps1`); elige por sí mismo el perfil GPU o CPU
(`-Cpu` fuerza la CPU). Después haz doble clic en `arayuz.cmd` para abrir la aplicación.
Todo se instala dentro de la carpeta del repositorio (`.venv`, `runtime_assets/`); cada descarga tiene versión fija y
se verifica con sha256. Disco libre para empezar: 22 GB con el perfil GPU, 14 GB solo CPU; uso medido tras la instalación ≈ 14,6 GB (GPU, archivos con enlaces duros contados una vez; el explorador muestra ≈ 22 GB). Comprobación: `.venv\Scripts\dubla.exe kontrol`.

Requisitos, orden de los pasos, mapa de entornos de Python, motores opcionales, uso sin conexión, actualización,
desinstalación y errores frecuentes (en inglés): **[docs/installation.md](docs/installation.md)**. Linux y macOS aún no se han probado.

## Uso

Aplicación de escritorio: doble clic en `arayuz.cmd` (aplicación web local: `web.cmd`, solo 127.0.0.1). Por ahora la interfaz de la aplicación está en turco. Desde la línea de comandos:

```powershell
.venv\Scripts\dubla.exe talk.mp4                            # recommended flow, Turkish dub
.venv\Scripts\dubla.exe talk.mp4 --ayar genel.hedef_dil=de  # another target language
```

Los resultados van a `cikti/<video>_<time>/`: `dubbed_tr.mp4` (con la etiqueta `AI-dubbed`), los subtítulos de origen `transcript_<lang>.srt` y los archivos JSON del trabajo; la última línea `dubbed_video:` muestra la ruta. Todos los ajustes: [docs/tarifler/kombinasyonlar.md](docs/tarifler/kombinasyonlar.md).

## Cómo funciona

1. **Audio:** FFmpeg extrae el sonido; Demucs opcional (MIT) separa la voz del fondo.
2. **Voz a texto:** faster-whisper large-v3-turbo (MIT) más tiempos por palabra con wav2vec2 CTC (inglés MIT, turco CC BY 4.0); opcional CrisperWhisper 2.0 (no comercial) y otros motores.
3. **Hablantes:** 3D-Speaker CAM++ (Apache-2.0) y un clasificador de género (Apache-2.0) eligen una voz sintética por hablante.
4. **Traducción:** Codex CLI o Claude Code CLI si están instalados y con sesión iniciada; si no, Opus-MT local de inglés a turco (CC BY 4.0); backends por API opcionales.
5. **Voz y tiempo:** Supertonic 3 (OpenRAIL-M) por defecto, VoxCPM2 (Apache-2.0) o XTTS-v2 (no comercial) opcionales; cada frase se acelera como mucho 1,25× hacia la duración del segmento original y el vídeo se reajusta para el resto, así que el doblaje puede durar más que el original.
6. **Vídeo:** FFmpeg escribe el audio nuevo, subtítulos SRT / VTT / ASS y la etiqueta `AI-dubbed`.

## Mediciones

Máquina de referencia: GPU Pascal de 4 GB, Windows 10; método y todas las filas en [docs/olcumler.md](docs/olcumler.md).

| Qué | Perfil CPU | Perfil GPU |
|---|---|---|
| Primera instalación, pasos por defecto, de principio a fin | ≈ 38 min | ≈ 44 min (paquetes 13,7 min) |
| Disco tras la instalación | ≈ 13,2 GB (suma de carpetas) | ≈ 14,6 GB (enlaces duros contados una vez) |
| Doblaje de la muestra de 9 s, traducción sin conexión | 528 s | 376 s |
| Clip en inglés de 30 s, Demucs, traducción con Claude Code | – | 744 s |

## Límites

- Sin CrisperWhisper (motor opcional 13), faster-whisper puede saltarse habla o inventar texto en chino y japonés (visto: se saltaron los primeros ≈ 10 s de un clip en chino; unos gritos se convirtieron en una larga línea "ああ…").
- La CI solo prueba la CPU; la ruta GPU se ejecutó a mano en una tarjeta Pascal de 4 GB. No se probaron tarjetas nuevas (RTX 50), Linux ni macOS; las bibliotecas GPU instaladas incluyen kernels de Pascal a RTX 50 y Maxwell usa el perfil CPU ([GPU runtime matrix](docs/installation.md#1-system-requirements)).
- El traductor sin conexión solo traduce de inglés a turco; otros pares necesitan Codex / Claude Code CLI o un backend por API.
- Tiempo por palabra para idiomas de origen distintos de inglés y turco: japonés y chino con `scripts/kur.ps1 -Adim hizalama-diller`, el resto tras una ejecución con `DUBLAJ_CEVRIMICI=1`.
- Sin probar de extremo a extremo: instalación real de XTTS-v2, RVC, el bot de Telegram contra el servicio real, motores CrisperWhisper; Moonshine es experimental.

## Bloques de construcción

Cada etapa funciona por separado, desde la línea de comandos o desde Python, con formatos de archivo documentados entre
etapas (mapa de etapas y esquemas JSON: [docs/mimari.md](docs/mimari.md)):

```bash
dubla yaziya-dok talk.mp4 -o talk.json          # speech-to-text + word times (also: indir, ses-cikar, ayir, hizala)
dubla cevir talk.json -o talk.tr.json            # translation, timing kept
dubla seslendir talk.tr.json -o tts/             # timed speech (or plain text -> WAV)
dubla altyazi talk.json --kip karaoke -o k.ass   # SRT / VTT / ASS, word and karaoke modes
dubla birlestir talk.mp4 -o out.mp4 --ses tts/speech.wav --altyazi talk.tr.srt
```

`from dublaj_hatti import api` ofrece las mismas etapas como funciones. Instala solo lo que necesita cada etapa, p. ej.
`pip install -e ".[stt,hizalama,cpu]"` para subtítulos. Cinco pequeñas herramientas hechas con estos bloques: [examples/](examples/).

## Proyectos relacionados

| Repositorio | Qué es | Cómo lo usa este repositorio |
|---|---|---|
| **DubWorld** (este repositorio) | cadena local de doblaje de vídeo de principio a fin; cada etapa se puede usar por separado | - |
| [crisperwhisper-turkce-kelime-zamani](https://github.com/alexturkey/crisperwhisper-turkce-kelime-zamani) | transcripción literal con marcas de tiempo por palabra (CrisperWhisper 2.0 Turbo + alineación CTC) | motor opcional 13: `scripts/kur.ps1 -Adim crisper` instala su modelo a través de ese repositorio en un commit fijo (pesos **solo no comerciales**) |
| [voxcpm2-turkce-ses-tasarimi](https://github.com/alexturkey/voxcpm2-turkce-ses-tasarimi) | diseño de voz y lectura con VoxCPM2, 8 idiomas, voces listas | motor TTS opcional `voxcpm2`: `scripts/kur.ps1 -Adim voxcpm2` lo instala en un commit fijo; este repositorio lo llama mediante un adaptador ligero |

Cada repositorio hermano mantiene su propia licencia, instalación e incidencias; los commits fijos hacen reproducible la combinación.

## Uso responsable

> **Aviso legal.** Eres el único responsable del contenido que procesas y publicas con este software y de cumplir las
> leyes de tu jurisdicción y las condiciones de los sitios y servicios que utilizas. El software se ofrece "tal cual",
> sin garantía (Apache-2.0). Texto completo y versión inglesa vinculante: [ETHICS.md](ETHICS.md).

- **Derechos y consentimiento.** Procesa solo material que sea tuyo o que tengas permiso para traducir y volver a
  doblar, y obtén el consentimiento de las personas identificables que aparezcan.
- **Voces.** Nada de suplantación. Una voz de referencia solo puede ser la tuya o una cuyo dueño haya dado su consentimiento explícito.
- **Etiquétalo.** Las salidas llevan una etiqueta de metadatos `AI-dubbed`; consérvala e indica también de forma visible
  a tu público que es un doblaje con IA (Ley de IA de la UE, art. 50; licencia de Supertonic).
- **Descargas.** Los extras opcionales `youtube` (yt-dlp) y `galeri` (gallery-dl) son para contenido que te pertenece o
  que puedes descargar; se aplican las condiciones del sitio y tu legislación local.
- **Motores no comerciales.** CrisperWhisper 2.0 y XTTS-v2 son solo para uso no comercial (desactivados por defecto).
  Revisa la columna **Commercial?** de [THIRD_PARTY.md](THIRD_PARTY.md) antes de cualquier trabajo de pago o para clientes.
  Los modelos de tiempo por palabra para audio de origen en fr / de / es / it (CC BY-NC 4.0) también son no comerciales y piden consentimiento en el primer uso.

## Ayuda y soporte

Preguntas, ideas y resultados: [Discussions](https://github.com/alexturkey/dubworld/discussions). Problemas de instalación: [issue de instalación](https://github.com/alexturkey/dubworld/issues/new?template=kurulum-sorunu.yml); errores: [informe de error](https://github.com/alexturkey/dubworld/issues/new?template=hata-raporu.yml)
(indica sistema operativo, GPU, el comando y sus últimas líneas). Fallos de seguridad: SECURITY.md, no en issues públicos.

## Licencia y créditos

Código: Apache-2.0 (LICENSE). Componentes de terceros y sus licencias: THIRD_PARTY.md. Uso responsable: ETHICS.md.
Privacidad (qué se queda en local, qué recibe un servicio en la nube): PRIVACY.md. Informes de seguridad: SECURITY.md. Cambios: CHANGELOG.md.

---

> This translation may lag; English is authoritative. Esta traducción puede ir con retraso; la versión inglesa es la que
> vale. Fuente: README.md (marca de sincronización abajo). Traducción automática (Claude); se agradecen PR de corrección.

<!-- i18n-source: README.md sha256:6829b755ca26 -->
