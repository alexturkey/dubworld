---
name: arayuz-tasarimi
description: "Rules for designing and changing the DubWorld web interface so it stays consistent, calm and helpful: colour/space/motion tokens, one icon per action, one confirm dialog for risky actions, no layout shift, deliberate motion, familiar placement, instant feedback, plain words (tr/en), accessibility, and a verification checklist. Use when adding or editing anything in web_statik (index.html, app.css, app.js), a button, icon, dialog, toast, list or setting, or when the user says 'interface', 'design', 'button', 'icon', 'delete', 'are you sure', 'jumps', 'layout shift', 'animation', 'arayüz', 'tasarım', 'düğme', 'simge', 'silme onayı', 'ekran kayıyor', 'hareket'."
---

# Interface design / Arayüz tasarımı

Türkçe özet en altta. / Turkish summary at the end.

## When to use

Any change under `src/dublaj_hatti/web_statik/` and any new screen text. The goal: a beginner never wonders what a
control does, nothing moves without a reason, nothing destructive happens by accident. Reuse what exists before
adding anything new; if a rule here and the code disagree, fix the code.

## 1. One source of truth

- Every colour, space, radius, shadow and duration is a CSS variable in `:root` of `app.css` (day), with the same
  names in the dark block and in the `prefers-color-scheme` block (a test checks both are identical).
- No hard-coded colour, size or duration in a rule. Need a new one? Add a token to all themes, then use it.
- Contrast stays at least 4.5:1 for text, no pure black or white (`tests/test_web_arayuz.py`). Add every new
  text/background pair to that test.
- Status colours mean one thing: `--tamam` done, `--hata` error or danger, `--uyari` caution, `--ana` primary.

## 2. One icon per action, everywhere

- Icons come only from the `<symbol id="s-...">` sprite in `index.html`; no emoji or text glyphs as icons.
- Fixed vocabulary (add to it, never vary it): trash = delete, two sheets = copy, pencil = rename, play = play/use,
  stop square = stop, x = close, upload arrow = add file, folder = open folder, check = done, sliders = settings.
- An icon never stands alone: a text label next to it, or `aria-label` plus `title` (tooltip) with the same words.
- The same verb for the same action in every screen and both languages (Use, Rename, Delete, Copy, Stop, Close).
- The danger colour is for Delete and Stop (on hover/focus and in the confirm dialog) and nothing else.

## 3. Risky and destructive actions

- One reusable in-page `<dialog>` confirm component, opened with `showModal()`. Never `window.confirm`,
  `alert` or `prompt`.
- Title names the thing ("Delete job #12?"), body says what is lost and whether it can be undone. Buttons:
  "Cancel" (left, default focus) and a red "Delete" (right, same verb as the trigger). Esc and backdrop click =
  cancel. Focus returns to the trigger.
- Ask exactly once: no confirm on top of a confirm, and no repeat per item inside a batch.
- Cheap and reversible actions (archive, hide, rename) get no dialog: do it, then show an Undo toast for about 6 s.
- Risky settings (licence-gated engines, large or paid downloads, overwriting output) use the same dialog and state
  the cost in plain words. A licence text is shown in the dialog, not in a browser popup.
- Stopping a running job asks first, because the work done so far is lost.

## 4. No layout shift

- Reserve space before content arrives: status line, error line, progress card and result card have a fixed or
  minimum height (use `visibility` instead of `hidden`/`display:none` when the neighbours must not move).
- Errors appear in a reserved slot next to the field or button, not by pushing the page down.
- Loading uses a skeleton or a placeholder of the final size; images and the player keep an `aspect-ratio`.
- Lists do not jump: adding or removing a row animates its height once (about 150 ms) or leaves a placeholder; the
  rows around it keep their position. Never re-render a whole list to change one row.
- Fonts and icons do not reflow: sprite icons have fixed `width`/`height`; numbers use
  `font-variant-numeric: tabular-nums`; system fonts, or `font-display: optional`.
- A button keeps its width when its label changes (set `min-width`; a spinner replaces the icon, not the text).
- Opening a drawer or dialog must not change the page width: `scrollbar-gutter: stable` on the scrolling root.
- Open panels with `transform`/`opacity`, not by animating the `height`, `top` or `left` of neighbours.

## 5. Motion is deliberate

The eye is pulled to anything that moves, so motion must earn its place.

- Motion only shows cause and effect (a panel opens, a row leaves, a value changed). 120-200 ms, ease-out,
  `transform` and `opacity` only, one thing moving at a time.
- No decorative loops. The only continuous motion allowed is the progress indicator of a running job, and it
  stops with the job. No auto-scrolling the user did not ask for.
- Celebrations (confetti) are one-shot, short, never block the screen, and are off with reduced motion.
- `@media (prefers-reduced-motion: reduce)` neutralises every `animation`, `transition` and JS smooth-scroll in one
  rule; add every new motion to it.

## 6. Placement people already know

- Primary action bottom-right of a form or dialog; Cancel to its left; a destructive action is never styled as
  primary and never sits tight against it.
- Search at the top of a list or drawer. Close (x) top-right of every dialog and drawer.
- Per-item actions sit on the right of the row in a fixed order: Use, Rename, Copy, Delete (delete last).
- Settings: label left, control right, one line of help under it; changed values are marked.
- Everything has one place: never the same control in two places with different behaviour.

## 7. Feedback within 100 ms

- Every control has hover, focus-visible, pressed and disabled states.
- A started action shows a spinner on the button itself and ignores repeat clicks; success shows a toast
  (3-4 s, `role="status"`, bottom, never covering the primary button); failure shows an inline error next to the
  thing that failed, with what to do next.
- No silent success and no silent failure.

## 8. Words

- Plain language for a beginner, no internal names; one sentence of help under every new feature.
- Same word for the same thing everywhere. Every visible string is an i18n key present in `tr.json` and `en.json`
  (placeholders kept, whole sentences, no glued fragments); `tests/test_arayuz_dili.py` must pass.
- Buttons say what they do ("Delete job", "Start dubbing"), not "OK" or "Yes".

## 9. Accessibility

- Visible focus (`:focus-visible`), full keyboard path, logical tab order, Esc closes the top layer.
- Touch targets at least 44x44 px (also in the job list, the player and segmented controls).
- Meaning never by colour alone (add an icon or text). Dialogs use `aria-labelledby`; toasts `role="status"`;
  errors `role="alert"`.

## 10. Verification checklist (before saying "done")

1. `python -m pytest tests/test_web_arayuz.py tests/test_arayuz_dili.py` passes.
2. Screenshots at desktop, half window (about 960 px) and narrow (420 px or less), light and dark, and once with
   reduced motion forced on. Look at them: nothing cut off, nothing overlapping.
3. Overflow: in each state `document.documentElement.scrollWidth <= clientWidth`.
4. Layout shift: attach a `PerformanceObserver({type:"layout-shift"})` before scripted actions (open the drawer,
   start and finish a job, add and remove a list row, switch language and theme); the summed value of shifts
   without recent input must stay below 0.02.
5. Every destructive action opens the shared confirm dialog; grep finds no `window.confirm`, `alert(` or new
   hard-coded colour.
6. Every icon-only button has `aria-label` and `title` in both languages.
7. New contrast pairs are in the contrast test.

## Türkçe özet

Tek kaynak: renk, boşluk, süre `app.css` değişkenlerinde; sabit renk yok. Her eylem için tek simge (çöp = sil, iki
sayfa = kopyala, kalem = adlandır) ve hep yazı ya da `aria-label` + ipucu. Silme ve riskli ayar: tek sayfa içi
`<dialog>` onayı (başlıkta adı, ne kaybolur, "Vazgeç" varsayılan, kırmızı "Sil"; Esc = vazgeç); ucuz, geri
alınabilir işte onay yerine "Geri al" bildirimi; `window.confirm` yok. Ekran kaymaz: durum, hata, yükleme için yer
ayrılır, listeler zıplamaz, düğme genişliği sabit. Hareket yalnız neden-sonuç için (en çok 200 ms), süs döngüsü
yok, `prefers-reduced-motion` hepsini durdurur. Bilinen yerleşim: ana eylem sağ altta, silme ayrı ve sonda, arama
üstte. 100 ms içinde geri bildirim. Sade dil, aynı eylem aynı kelime. 44 px dokunma alanı, odak görünür. Bitirmeden:
ekran görüntüleri (gündüz/gece/dar/hareket azaltılmış), taşma ve kayma (CLS < 0,02) ölçümü.
