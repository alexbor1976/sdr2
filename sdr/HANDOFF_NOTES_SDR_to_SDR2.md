# sdr2 — handoff notes from planning chat (2026-07-13)

> Paste this into a fresh chat when starting work on `sdr2`, alongside
> `HARDWARE_NOTES.md`. It captures decisions made while planning the project,
> not hardware facts (those live in `HARDWARE_NOTES.md`).

## Lineage

`sdr2` is a reorganized follow-on to an earlier project (`sdr`), a remote
spectrum analyzer / signal generator built on an ADRV9364-Z7020 SOM. The code
is being restructured into a different file layout of the user's own design.
The original project's README has the phase-by-phase build log if deeper
history is ever needed — it is not being carried over file-by-file, only its
facts.

## Current hardware state (also in HARDWARE_NOTES.md — kept in sync there)

- Antennas are now physically connected: **RXA** ← Molex 105263 Series
  Flexible Cellular 6-Band Antenna; **TXA** ← Siretta Delta 2 Series
  Right-Angle Stubby Antenna. This is **not** an empty-SMA / digital-loopback-only
  bench setup anymore — any TX buffer radiates for real.
- Signal generator frequency changed from the original tutorial default
  (100 MHz) to **433 MHz**, checked for legal use in this band/region.
- `tx_hardwaregain_chan0` should stay conservative (large negative =
  more attenuation) until radiated power has actually been measured.

## Decisions made about how sdr2 is organized

- **One folder/repo per iteration, not branches.** This is a genuine
  restructuring, not a variant — a fresh repo for `sdr2` was chosen over a
  branch of the old one.
- **Docs consolidated to two files instead of five.** The original project had
  README + GUIDE + AI_CONTEXT + HARDWARE_NOTES + NOTES, which was too many
  entry points. `sdr2` collapses this to:
  - **`CONTEXT.md`** — static facts: hardware quirks, architecture, safety
    constraints, repo layout, "how to prompt an AI about this project." This
    is what gets pasted into a new chat. `HARDWARE_NOTES.md` content folds
    into this file rather than staying separate — one file to keep updated,
    not two.
  - **`LOG.md`** (optional, add only if it earns its keep) — a running lab
    notebook, one line per notable event: date, machine, command, expected,
    observed, conclusion. Its value is mainly for **failures and surprises**
    worth remembering later, not a log of every successful run. Skip it
    entirely if it feels like overhead — revisit once a confusing bug shows up
    that's worth having written down.
- **No live link between old and new projects.** Claude Projects don't cross-reference
  each other. Carrying facts forward means copying them once, deliberately —
  not re-copying docs wholesale. A single pointer line at the top of the new
  `CONTEXT.md`/`HARDWARE_NOTES.md` credits the original project; see the
  existing `HARDWARE_NOTES.md` for the exact wording used.
- **Markdown, not plain text**, for these docs — renders on GitHub, previews
  in VS Code (`Ctrl+Shift+V`), and only needs a handful of syntax elements
  (`#` headings, `**bold**`, `- bullets`, `` `code` ``) to be useful.
- **`.gitignore` for Python** was flagged as worth adding (`__pycache__/`,
  `venv/`, `*.pyc`) — not yet generated.

## Open / next step

User is about to ask for program code to be **recreated** from the original
`sdr` project, reorganized into `sdr2`'s own file structure. No specific new
layout has been specified yet in this chat — that's the next decision point.
