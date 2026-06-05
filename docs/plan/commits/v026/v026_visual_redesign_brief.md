# v0.2.6 — visual redesign brief (anchor: shadcn/ui)     release: v0.2.6 · phase: redesign

> **Status: reference LOCKED, implementation NOT yet planned.** The commit sequence + exact token diffs
> are planned in a NEW chat (user's call). This doc captures the DIRECTION so that planning session can
> start cold. Read with: DECISIONS **ADR-42** (the component-system foundation) + **ADR-43** (this
> deviation + the collapsed release), the c16x as-built (QUALITY_GATES **§21.1u**), and the approved plan
> `~/.claude/plans/bobframes-v0-2-5-continue-staged-octopus.md` (the v0.2.6 commit sequence + review notes).

## Context

c16x (ADR-42) shipped the component-system FOUNDATION at visual parity (CSS/JS in real files; the
escape-by-construction `el` builder; the token-validity guard; the table component family built; summary
migrated off its inline `<style>`). That is invisible plumbing. **v0.2.6 is the user-facing payoff: a real
visual redesign.** Per ADR-43 there is **no standalone 0.2.5 release** — v0.2.6 is the next PyPI release and
carries BOTH the foundation (c16q–c16x) AND the redesign; `_version` jumps `0.2.0 → 0.2.6`.

The user chose **[ui.shadcn.com](https://ui.shadcn.com)** as the visual anchor — specifically the blend
**"shadcn for the SYSTEM + a dash of Grafana for the data-dashboard DENSITY."** shadcn supplies the visual
language (palette, borders, radius, component shapes, states); Grafana informs how TIGHT it packs (our
reports are dense tables + KPI grids + drill views — shadcn's airy marketing-gallery defaults would waste
space). See **Density** below — it is a load-bearing part of the direction, not a footnote.

## Quality bar (NON-NEGOTIABLE — this is a big quality overhaul, not a reskin)

The user's mandate: **clean, components, no bespoke stuff.** v0.2.6 is where the "everything is a component"
goal is fully realized (c16x built the machinery; v0.2.6 adopts it everywhere).
- **No bespoke markup or CSS.** By the end, EVERY visual element is a named, single-source component built
  through `chrome.el` (escape-by-construction) + the owned token/CSS bundle. Target: zero per-call
  hand-concat `h()`, zero one-off `<style>`/inline `style=` beyond intrinsically data-driven values (a
  bar's `width:%`), zero page that hand-writes a `<table>`/card/badge/section.
- **Adopt, don't add.** Migrate the ~117 hand-written table sites onto `data_table`/`static_table`; roll the
  remaining chrome / delta / charts / dashboard / template leaves onto `el`. **Epic-wide, not one commit** —
  track the long tail as a checklist so nothing stays bespoke. The redesign goldens change anyway, so this
  is the moment the byte-parity barrier (which blocked it in c16x) is gone.
- **Every component in the gallery.** The preview gallery renders one instance of every component (incl. the
  catalog/drill hierarchy) — the living catalog + the review surface.
- **Guards stay green.** Token guard = 0 undefined refs; a structural/ARIA test per component; data path
  frozen (`test_parquet_parity`, never `make_parquet_golden`); all ADR-37 invariants hold.
- **Taste gated by screenshots.** Preview-gallery then per-surface headless-Chrome screenshots
  (light/dark/print, synthetic + real Perf) signed off BEFORE goldens land.

## Reconciliation: "bold" now means shadcn-clean, NOT loud

An earlier decision said "bold redesign," and the approved plan sketched a maximalist take (2.75rem hero
numerals, heavy accent rails). **shadcn moderates that.** shadcn's identity is **restrained, neutral, flat,
high-craft**: near-grayscale palette, a single near-black/near-white "primary," hairline borders doing the
separation (not heavy shadows), generous radius, tight readable type, color reserved for data (charts) and
status. So the redesign is "bold" in the sense of *a genuine modern overhaul*, but the **target aesthetic is
clean/quiet/neutral, not loud.** The new-chat planner should treat **shadcn as the definitive anchor** and
DISCARD the earlier hero-numeral/accent-rail maximalism where it conflicts. **But clean/neutral is NOT
loose:** pair shadcn's restraint with **Grafana density** (next section) — our data surfaces pack tight,
they don't float in whitespace. The blend is *shadcn surfaces + Grafana density*.

## The shadcn design language (what defines the look)

- **Near-neutral palette.** Almost everything is grayscale oklch (chroma 0): background, card, muted,
  border, foreground. Hue appears only in `--chart-1..5` (categorical data) and `--destructive` (red).
- **One neutral "primary."** Interactive/emphasis = near-black in light / near-white in dark
  (`--primary`), NOT a brand hue. (Decision for us below — we likely keep a functional accent hue for
  links/data; see mapping.)
- **Border-led separation, flat elevation.** Cards sit on the same background and are separated by a
  **hairline border** (`oklch(0.922 0 0)` light, `white/10%` dark) + radius, with minimal/no shadow.
  This is the REVERSE of our ADR-34 "depth over borders" — reconcile (see open decisions). Prints well.
- **Generous radius.** `--radius: 0.625rem` (~10px) with derived sm/md/lg. We currently hardcode `4px`.
- **Muted secondary text.** `--muted-foreground` (`0.556` light / `0.708` dark) for captions/meta.
- **Semantic `-foreground` pairing** (surface ↔ its text color).

### shadcn tokens (verbatim, oklch) — the source values to translate

```css
/* light (:root) */
--radius: 0.625rem;
--background: oklch(1 0 0);          --foreground: oklch(0.145 0 0);
--card: oklch(1 0 0);                --card-foreground: oklch(0.145 0 0);
--primary: oklch(0.205 0 0);         --primary-foreground: oklch(0.985 0 0);
--secondary: oklch(0.97 0 0);        --secondary-foreground: oklch(0.205 0 0);
--muted: oklch(0.97 0 0);            --muted-foreground: oklch(0.556 0 0);
--accent: oklch(0.97 0 0);           --accent-foreground: oklch(0.205 0 0);
--destructive: oklch(0.577 0.245 27.325);
--border: oklch(0.922 0 0);          --input: oklch(0.922 0 0);   --ring: oklch(0.708 0 0);
--chart-1: oklch(0.646 0.222 41.116);  --chart-2: oklch(0.6 0.118 184.704);
--chart-3: oklch(0.398 0.07 227.392);  --chart-4: oklch(0.828 0.189 84.429);
--chart-5: oklch(0.769 0.188 70.08);

/* dark (.dark) */
--background: oklch(0.145 0 0);      --foreground: oklch(0.985 0 0);
--card: oklch(0.205 0 0);            --card-foreground: oklch(0.985 0 0);
--primary: oklch(0.922 0 0);         --primary-foreground: oklch(0.205 0 0);
--secondary: oklch(0.269 0 0);       --muted: oklch(0.269 0 0);   --accent: oklch(0.269 0 0);
--muted-foreground: oklch(0.708 0 0);
--destructive: oklch(0.704 0.191 22.216);
--border: oklch(1 0 0 / 10%);        --input: oklch(1 0 0 / 15%); --ring: oklch(0.556 0 0);
--chart-1: oklch(0.488 0.243 264.376); --chart-2: oklch(0.696 0.17 162.48);
--chart-3: oklch(0.769 0.188 70.08);   --chart-4: oklch(0.627 0.265 303.9);
--chart-5: oklch(0.645 0.246 16.439);
```

## Density — the Grafana dash (the counterweight to shadcn's airiness)

shadcn supplies the **system** (palette / borders / radius / component shapes / states). Grafana supplies
the **density**: a perf dashboard packs information — tight rows, compact panels, data-first, high
information-per-screen. shadcn's defaults are generous (airy padding, big gaps, 10px radius) and would
**waste space on our dense tables / KPI grids / drill views**. So: adopt shadcn's LOOK, but pack it
TIGHTER than shadcn's marketing-gallery spacing. Concretely (the planner tunes exact values):
- **Tables (the densest surface).** Compact row height + cell padding (our `rdc-table` `--clip-cap` /
  `ROW_H` / `td` padding stay tight — do NOT inflate to shadcn's roomy table). Tabular-nums. Hairline
  row separation (shadcn `--border`), zebra optional. Drill/catalog optimize data-per-screen.
- **KPI grid.** More cards per row + tighter gaps than a shadcn card grid (the dashboard reads like a
  panel wall, not a landing page).
- **Card / section padding.** A notch tighter than shadcn defaults; smaller radius on dense minis than on
  hero cards (a radius SCALE, not one big 10px everywhere).
- **Spacing scale.** Keep our 4px base; lean on the SMALLER steps (sp-2/sp-3) for dense contexts; reserve
  the generous shadcn-like spacing for the summary one-pager (the one exec/airy surface).
- **Net:** "shadcn surfaces, Grafana density." The summary one-pager may be the airy exception; the
  dashboard / reports / drill are dense. Density is a per-surface dial, not one global value.

## Mapping shadcn → bobframes tokens (`reports/design_tokens.toml`)

Our tokens are already oklch + `light-dark()` (one source, both themes) — so this is mostly a re-tuning of
VALUES, not new machinery. Component class NAMES do **not** change (JS-coupled classes must not be renamed;
see c16x). `light-dark(LIGHT, DARK)` packs shadcn's `:root`/`.dark` pair into one declaration.

| shadcn | bobframes token | note |
|---|---|---|
| `--background` | `--bg` / `--surface-0` | white / `0.145` |
| `--card` | `--surface-1` | **flat**: light card == bg, separated by border (reconcile vs our tinted surfaces + ADR-34) |
| `--secondary`/`--muted`/`--accent` | `--surface-2` | the subtle fill: badge bg, row hover, code bg |
| `--foreground` | `--fg` / `--text-1` | `0.145` / `0.985` |
| `--muted-foreground` | `--text-2`, `--text-3` | secondary/tertiary meta (our `--text-3` AA fix stays) |
| `--border` | `--border` / `--border-1` | hairline `0.922` / `white 10%` |
| `--input` / `--ring` | focus-visible ring (`--accent`-driven today) | adopt `--ring` for focus outlines |
| `--primary` | `--accent-primary` | shadcn = NEUTRAL near-black/white. **Open:** keep a hue accent for links/data, or go neutral? (see below) |
| `--destructive` | `--status-alarm` | red. Our `--status-ok/warn/info` (green/amber/blue) have NO shadcn equiv → **keep** (domain-semantic) |
| `--chart-1..5` | `--c-*` (draw classes) + `--accent-data` | our draw-class colors are SEMANTIC → keep the mapping, optionally retune hues toward shadcn's chart vibrancy |
| `--radius: 0.625rem` | **NEW `--radius` token** | we hardcode `4px` today → introduce a radius token (~6–10px), guard-covered |

## Open decisions for the new-chat planner (do not pre-decide here)

1. **Flat (border-led) vs depth (ADR-34 shadows).** shadcn is flat + hairline borders; ADR-34 chose depth.
   Going shadcn-flat reverses ADR-34 → needs an ADR note. (Flat also prints better.) **Recommend: adopt
   shadcn-flat; record the ADR-34 reversal.**
2. **Neutral primary vs hue accent.** shadcn's `--primary` is neutral; our reports lean on a blue accent +
   a data accent + draw-class colors. **Recommend: chrome goes neutral (shadcn), but KEEP a functional
   accent hue for links/interactive + the data/chart palette** (reports are data-dense; all-neutral would
   bury the data). Decide the exact accent hue.
3. **Radius value** (4px → ~6/8/10px) + whether tables/dense minis use a tighter radius.
4. **Type scale.** shadcn documents no special scale (Geist/Inter, restrained). Keep vendored **Inter ≤600**;
   modest scale tune only (DROP the 2.75rem hero-numeral idea unless a KPI clearly benefits). Tabular-nums on numbers.
5. **Chart palette retune** toward shadcn `chart-1..5` vibrancy while keeping draw-class semantics.
6. **Density targets (the Grafana dash).** Exact `rdc-table` row height + cell padding, KPI grid columns +
   gaps, card/section padding, and the radius SCALE (tight minis vs hero cards). Which surfaces are airy
   (summary one-pager) vs dense (dashboard / reports / drill). **Recommend: pack tighter than shadcn
   defaults everywhere except the summary one-pager.**

## Constraints (unchanged — ADR-37, hold throughout)

Static / server-baked / JS-optional / printable / Ctrl-F-able / `file://`-safe / offline / deterministic /
ASCII. Vendored **Inter (weight ≤ 600)**. oklch via `light-dark()`. No new runtime dep / build step. The
token guard (c16x-3) auto-covers any new `var(--…)`. **Golden refreshes run ONLY on the canonical env
(py3.12 / pyarrow 21)** — never an out-of-range local pyarrow (the `golden_env` marker / ADR-11 / today's
CI fix). Component class names are frozen where JS queries them (rdc-table engine etc.).

## Replacement gates for the redesign (byte-parity intentionally broken — ADR-43)

(a) `test_parquet_parity` BYTE-UNCHANGED (data path untouched; never `make_parquet_golden`). (b)
golden-INDEPENDENT structural + ARIA component tests (mirror `test_report_structure`/`test_components`).
(c) the token guard. (d) **mandatory headless-Chrome browser matrix** — light/dark/print, synthetic +
real Perf at `c:/tmp/perf`, per changed surface (a repeatable screenshot harness is recommended). (e)
lint/ASCII/determinism. Goldens (`make_golden` + `make_preview_golden` + `make_package_golden`) refreshed
per intentional-visual commit, reviewed, on the canonical env; `_pagedata/*.js` stays byte-stable.

## Commit sequence (from the approved plan; the new chat finalizes/IDs them)

`v0.2.6` namespace (NOT `c20` — reserved for the v0.3 `--json` contract). Approved-plan shape:
1. **ADR-43 + all-chrome token/CSS lift** — translate shadcn into `design_tokens.toml` + the chrome CSS
   (palette, border-led surfaces, radius token, states, type tune). No body-markup change → every page lifts.
   (Review note: split into **1a** tokens/type/spacing — owns the pinned `test_design_tokens` byte updates —
   and **1b** flat-surfaces/radius/states/responsive/print, landed back-to-back.)
2. **Summary one-pager** restructure (compose the promoted components) — the ONE airy/exec surface.
3. **Dashboard grid** (cards in the shadcn idiom, **Grafana-dense**: more cards/row, tight gaps — a panel wall).
4. **6 detail reports** (shadcn surfaces, **dense** tables/cards).
5. **Catalog/drill** wide layout, **maximize data-per-screen (densest surface)** + **adopt the table component
   family** (c16x-4) across the reports here (where the golden refresh absorbs the normalization the parity
   gate forbade; keep the tight `rdc-table` row height) + roll remaining hand-concat leaves onto `el`.
6. **Close-out:** `_version 0.2.0 → 0.2.6`, ONE CHANGELOG `[0.2.6]` covering c16q→redesign, full matrix,
   real-Perf eyeball, tag → PyPI (AUTHORIZE FIRST — outward/irreversible).

## First move for the new chat
WebFetch shadcn (theming + a couple component pages), translate the token table above into
`design_tokens.toml` + the chrome CSS, render the **preview gallery** (every component, no data) to
light/dark/print screenshots, and get sign-off BEFORE touching data-page goldens.
