# Getting started (no programming needed)

[Türkçe](baslarken.md) · Full installation reference: [installation.md](installation.md)

This program takes a video, listens to what is said, translates it and makes a new copy of the video in which a
computer voice speaks the translation, with subtitles. Everything runs on your own computer; your video is not
uploaded anywhere (one exception, explained under "Choose another language").

## What you need

- A **Windows 10 or 11** computer (64-bit). Mac and Linux have not been tested yet.
- **Free disk space:** about 22 GB if the computer has an NVIDIA graphics card, about 14 GB if it does not. A measured install with an NVIDIA card uses about 14.6 GB; Windows Explorer shows about
  22 GB because a download cache shares most of its files with the program and Explorer counts them twice.
- **Internet** during the installation only.
- A **graphics card** is optional. A *graphics card* (also called *GPU*) is the part of the computer that draws the
  picture; NVIDIA cards can also do the heavy work of this program and make it much faster. Without one, the
  *processor* (*CPU*, the computer's main chip) does everything, only more slowly.
- A video you are **allowed to use**: your own, or one whose owner agreed.

## Install, the easy way: ask your AI assistant

An *AI assistant* here means a program such as Claude Code, Codex or Gemini CLI that can run commands on your
computer for you. Open it and paste this one sentence (the address is the page where you found this program):

```text
Install the video dubbing program from https://github.com/alexturkey/DubWorld on this computer. Follow the AGENTS.md file in that repository step by step, detect my hardware yourself and do not ask me technical questions. When `dubla kontrol` says READY and the sample dub works, open the program's window for me.
```

The assistant measures the computer and chooses the GPU or CPU setup by itself. Then it asks you, once and in plain
words, **what kind of setup you want**: quick, recommended for your computer, or full; it tells you what each part
does, how much disk space and time it needs and what its license allows. It also asks whether you accept the terms
of use of the voice the program speaks with. In short they say: do not imitate real people, do not deceive, and
tell your viewers that the voice is computer-made. If you agree, answer "yes". Then it downloads everything, tests
it on a small sample video and opens the program window. The program's window is in Turkish for now.

The download is about 13 GB (9.5 GB without an NVIDIA card); measured first installs took about 38 minutes (without an NVIDIA card) and about 44 minutes (with one; most of it
was the model download). A faster connection is quicker.

## Install, by yourself

1. On the project page click the green **Code** button, then **Download ZIP**. Unpack the ZIP into a short folder
   without spaces, for example `C:\dublaj`.
2. In that folder double-click **`kur.cmd`**. If Windows shows a blue "Windows protected your PC" window, click
   **More info**, then **Run anyway** (only if you downloaded the program from its official page).
3. A black window shows the progress. Do not close it. When it shows **Install finished**, press any key.
   If it shows **KURULUM DURDU / INSTALL STOPPED**, the lines below it say what to do; usually it is enough to
   double-click `kur.cmd` again (it continues where it stopped).

## Your first dub

1. In the program folder double-click **`arayuz.cmd`**. The program window opens. The window is in Turkish; the
   word list below translates every button.
2. Stay on the first tab, **Önerilen akış** (recommended flow). Click **Video seç…** and choose your video.
3. Under **Dublaj dili** (dubbing language) pick the language. Every language is written in its own words
   (Türkçe, English, Deutsch, Français, 日本語 …); Türkçe is selected unless you change it. The big button takes the
   language's name: **Türkçe dublajla**, **English dublajla**, **Deutsch dublajla** …
4. Click that button (**Türkçe dublajla** = dub into Turkish). The first time a window asks you to accept the voice's terms of
   use (see above); click **Yes** if you agree.
5. Wait. The bar at the bottom shows how far it is. On a computer without an NVIDIA graphics card it is slower.
6. When it says **Bitti** (done), click **Videoyu aç** (open video) to watch it, or **Çıktı klasörünü aç** (open the
   output folder). Results are kept in the `cikti` folder inside the program folder.

If the window shows a red line **Kurulum tamamlanmamış** (installation not finished), double-click `kur.cmd` again,
then reopen the program.

Button words: *Video seç…* = choose video · *ya da bağlantı* = or a link · *Dublaj dili* = dubbing language ·
*Türkçe dublajla* / *English dublajla* = dub into Turkish / English ·
*Yalnız altyazı / metin çıkar* = subtitles or text only · *Gelişmiş* = advanced settings · *İşler* = jobs (history,
continue a stopped job) · *Durdur* = stop · *Videoyu aç* = open video · *Çıktı klasörünü aç* = open output folder ·
*Günlüğü göster* = show the log (technical details).

## Choose another language

The program dubs into **Turkish** unless you change it. Pick another language in the **Dublaj dili** list on the
first tab; the button changes with it (for example **Deutsch dublajla**). The list and the `genel.hedef_dil` row on
the **Gelişmiş** tab are the same setting: change one and the other follows. The list shows only the languages the
selected voice engine can speak; a language marked *denenmedi* (not tested) works but has not been checked by ear.
The web page (`web.cmd`) has the same list.

The translator that comes with the program works only **from English into Turkish**, without internet. For any
other pair the program needs an online translator: the Codex or Claude Code assistant (used automatically when one
of them is installed and signed in) or a key for a translation service. In that case the *text* of the video, not
the video, is sent to that service. Easiest: ask your assistant, for example "set up translation into German for
the dubbing program".

## Words used here

| Word | Meaning |
|---|---|
| Dub, dubbing | replacing the speech of a video with speech in another language |
| GPU / graphics card | the computer part that draws the picture; an NVIDIA one makes this program faster |
| CPU / processor | the computer's main chip; it can do all the work, only more slowly |
| Model | a large file the program learned from; it is downloaded once during installation |
| Install | putting the program and its models on the computer (everything goes into the program folder) |
| Subtitle | the written text shown at the bottom of the video |
| `AI-dubbed` tag | a hidden note inside the result file saying that a computer made the voice; keep it |
| Log | a technical diary of what the program did; useful to send to your assistant when something goes wrong |

## Common problems

| What you see | What to do | Or tell your assistant |
|---|---|---|
| **KURULUM DURDU / INSTALL STOPPED** in the install window | double-click `kur.cmd` again; it continues where it stopped | "The installation stopped with this message: … Please fix it." |
| "running scripts is disabled on this system" | use `kur.cmd`, not the files in the `scripts` folder | "Install it with the AGENTS.md steps." |
| The install says there is not enough disk space | free some space (about 22 GB, 14 GB without an NVIDIA card) or put the folder on another drive | "Move the dubbing program to drive D: and finish the installation." |
| The program window shows a red **Kurulum tamamlanmamış** line | double-click `kur.cmd` again, then reopen the window | "Check the dubbing program's installation and fix what is missing." |
| Dubbing is very slow | normal without an NVIDIA graphics card; with one, the card may not be in use (often an old driver) | "Check whether the dubbing program uses my graphics card." |
| A window asks about a **license** | read it; it is the voice's terms of use. Accept only if you agree | – |
| Error about translation or language | the built-in translator does only English → Turkish; see "Choose another language" | "Set up translation from Spanish into Turkish for the dubbing program." |
| **İş başarısız** (job failed) | open the **İşler** tab; a stopped job can be continued there. Click *Günlüğü göster* and copy the last lines | "My dub failed; here is the log: … Please fix it." |
| You want to remove the program | delete the program folder; nothing else was changed on the computer | – |

## Please use it responsibly

Dub only videos you own or may use, and do not imitate real people's voices. Tell your viewers that the dubbing
was made with AI. The details are in [../ETHICS.md](../ETHICS.md) and what stays on your computer is in
[../PRIVACY.md](../PRIVACY.md).
