---
version: alpha
name: FocusIn-design-analysis
description: The design language of 聚光 FocusIn, a local-first message-aggregation + AI-agent platform. The brand metaphor is a spotlight: one warm amber gradient band ("今日聚光") concentrates attention while everything else stays quiet — warm near-white surfaces, a single restrained brand orange used sparingly for focus states, and a dark warm-neutral ink for the strongest CTA. Figtree (Latin) paired with PingFang SC (CJK) carries a compact 13.5px dashboard body, tabular figures everywhere numbers appear, two-layer soft shadows, 12px card radii on an 8pt grid, spring-curve micro-interactions, and staggered list entrances. The tone is calm, warm, and trustworthy — a tool that helps you read less, not more.

colors:
  # Brand (warm spotlight amber)
  brand: "#ef8b23"
  brand-strong: "#d9741a"
  brand-weak: "#fdeed9"
  grad-a: "#f5a623"
  grad-b: "#ef7d2e"
  grad-c: "#d9541a"

  # Surfaces (warm near-whites)
  bg: "#faf9f7"
  surface: "#ffffff"
  surface-2: "#f4f2ef"

  # Ink
  text: "#1d1c1a"
  text-2: "#6f6c66"
  text-3: "#a19d95"
  line: "#ecebe7"

  # Semantic
  ok: "#2f9e6e"
  warn: "#e03131"

  # Group badges (tonal fills)
  grp-todo-bg: "#fdeed9"
  grp-todo-fg: "#b05e00"
  grp-schedule-bg: "#e1efff"
  grp-schedule-fg: "#1c6edb"
  grp-notice-bg: "#e3f7f1"
  grp-notice-fg: "#0e8a70"
  grp-important-bg: "#ffe7e7"
  grp-important-fg: "#d0342c"
  grp-chatter-bg: "{colors.surface-2}"
  grp-chatter-fg: "{colors.text-3}"

  # Channel dots
  ch-wechat: "#07c160"
  ch-feishu: "#3370ff"
  ch-dingtalk: "#0089ff"
  ch-email: "#ff9d00"
  ch-qq: "#12b7f5"

typography:
  display-hero:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: clamp(22px, 2.6vw, 28px)
    fontWeight: 800
    lineHeight: 1.22
    letterSpacing: -0.03em
    textWrap: balance
  heading-lg:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 16px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: -0.01em
  stat-xl:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.02em
    fontVariantNumeric: tabular-nums
  body-md:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 13.5px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  body-card:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 13.5px
    fontWeight: 500
    lineHeight: 1.55
  caption-md:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
  label-sm:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.5
  badge-sm:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
  button-md:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.0
    letterSpacing: -0.01em
  button-sm:
    fontFamily: "Figtree, 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.0

rounded:
  sm: 8px
  md: 12px
  pill: 999px

spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
  xxl: 24px
  xxxl: 32px

motion:
  ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)
  ease-out: cubic-bezier(0, 0, 0.2, 1)
  duration-fast: 150ms
  duration-base: 250ms

components:
  button-primary:
    backgroundColor: "#241f1a"
    textColor: "#ffffff"
    typography: "{typography.button-md}"
    rounded: "{rounded.pill}"
    height: 38px
    padding: 0 22px
    boxShadow: inset 0 1px 0 rgba(255, 255, 255, 0.09)
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    borderColor: "{colors.line}"
    typography: "{typography.button-md}"
    rounded: "{rounded.pill}"
    height: 34px
    padding: 0 16px
  button-on-hero:
    backgroundColor: "#ffffff"
    textColor: "#7a3a0a"
    typography: "{typography.button-md}"
    rounded: "{rounded.pill}"
    height: 38px
    padding: 0 22px
  card:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line}"
    rounded: "{rounded.md}"
    boxShadow: "0 1px 2px rgba(29,28,26,0.05), 0 4px 16px rgba(29,28,26,0.06)"
  card-hover:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    boxShadow: "0 4px 8px rgba(29,28,26,0.08), 0 12px 32px rgba(29,28,26,0.12)"
    transform: translateY(-2px)
  hero-spotlight:
    background: radial-gradient(520px 260px at 12% -10%, rgba(255,235,200,0.22), transparent 65%), linear-gradient(115deg, #f9bd4a 0%, #f5a623 36%, #ef7d2e 68%, #d9541a 100%)
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: 24px 32px
  badge-group:
    typography: "{typography.badge-sm}"
    rounded: "{rounded.pill}"
    padding: 2px 9px
  text-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body-md}"
    rounded: "{rounded.pill}"
    borderColor: "{colors.line}"
---

## Overview

聚光 FocusIn ("Focus Light") is a local-first dashboard that aggregates messages across WeChat / Feishu / DingTalk / Email / QQ, auto-triages them into 待办 / 日程 / 通知 / 重要 / 闲聊 groups, and lets an AI agent act on them behind a human-approval gate. The design language encodes that product promise: **one warm spotlight band per screen, everything else recedes.**

The overview page opens with the **hero-spotlight** — a 4-stop warm amber gradient band (top-left cream glow, amber → deep-orange descent, bottom-right ember vignette) with white display text and a single white pill CTA. Below it, the page returns to warm near-white canvas (`{colors.bg}` #faf9f7): channel stat cards, a message-card stream, a digest table, and a stats panel. Dark warm-neutral ink (`#241f1a`) is reserved for the strongest action on light surfaces; brand orange is used sparingly for focus rings, emphasis, and hot counts — never as body text.

Typography pairs **Figtree** (Latin: geometric-humanist, distinctive at weight 800) with **PingFang SC / Microsoft YaHei** (CJK). The body tier is a compact 13.5px dashboard scale; every numeric role — channel counts, message counts, timestamps, ring percentages — renders with `font-variant-numeric: tabular-nums`, the system's quiet data signature.

Depth is two-layer soft shadow on an 8pt spacing grid; radii are 12px for cards, 8px for nested elements, pills for buttons and badges. Motion is spring-curve micro-interaction plus a 0.05s-per-item stagger fade-up on every card list, guarded by `prefers-reduced-motion`.

**Key Characteristics:**
- Spotlight hero: 4-stop warm amber gradient band with layered radial glows, white 800-weight display type, white pill CTA — one per screen, never repeated below the fold.
- Single-hue restraint: brand orange appears only as focus/emphasis; near-black warm ink (#241f1a) is the primary CTA fill on light surfaces.
- Tabular figures on all numeric cells — counts, timestamps, percentages.
- Two-layer shadows (contact + ambient) that deepen on hover with a -2px spring lift.
- Tonal group badges (amber/blue/teal/red/neutral fills at ~10% saturation) that never fight the hero for attention.
- Staggered fade-up entrances on every card list; ripple pulse on inbound messages; twinkle ✦ ornaments inside the hero only.
- Full dark theme via `[data-theme="dark"]` re-tokenization (no per-component overrides).

## Colors

> **Source pages:** 纵览 `/` · 消息流 · 日历 · 对话 · 设置.

### Brand & Accent
- **Brand** (`{colors.brand}` — `#ef8b23`): the spotlight amber. Focus rings, links, hot-count emphasis, the stat ring. Used sparingly — a little goes a long way.
- **Brand Strong** (`{colors.brand-strong}` — `#d9741a`): hover / pressed lifts of the brand, hot-state text.
- **Brand Weak** (`{colors.brand-weak}` — `#fdeed9`): amber-tinted fill for selections and soft highlights.
- **Hero Gradient** (`{colors.grad-a/b/c}` + `#f9bd4a` top stop): the 4-stop spotlight band. Deepens toward the right and bottom — the light "focuses" as it descends.

### Surfaces
- **Bg** (`{colors.bg}` — `#faf9f7`): page background; warm, not pure white.
- **Surface** (`{colors.surface}` — `#ffffff`): card fill.
- **Surface-2** (`{colors.surface-2}` — `#f4f2ef`): nested / tonal fills, table hover, chatter badge.

### Ink
- **Text** (`{colors.text}` — `#1d1c1a`): warm near-black body ink. Never pure black.
- **Text-2 / Text-3** (`{colors.text-2}` `#6f6c66` / `{colors.text-3}` `#a19d95`): secondary / tertiary hierarchy.
- **Primary CTA fill** (`#241f1a`): the darkest ink in the system, reserved for the one primary button per view.

### Semantic & System
- **Ok / Warn** (`{colors.ok}` `#2f9e6e` / `{colors.warn}` `#e03131`): confirm and destructive actions.
- **Group badges**: five tonal pairs (todo=amber, schedule=blue, notice=teal, important=red, chatter=neutral). All ~10% tinted fills with deep-tone text — legible at 11px, quiet at rest.
- **Channel dots**: 8px circles keyed to real brand colors (WeChat green, Feishu blue, DingTalk blue, Email orange, QQ cyan) — the only place third-party hues are allowed.

### Dark Theme
`[data-theme="dark"]` swaps the token layer: bg `#141312`, surface `#201f1d`, ink `#f0eeea`, amber tints deepen (`#3a2c17`), shadows go black-based. Components consume tokens only, so the flip is total.

## Typography

### Font Family
**Figtree** (Latin, Google Fonts) at weights 400–800, paired with **PingFang SC** / **Microsoft YaHei** for CJK. The 800-weight hero with -0.03em tracking is the display signature; Inter or Poppins at 800 with the same tracking is an acceptable substitute when Figtree is unavailable.

### Hierarchy

| Token | Size | Weight | Line Height | Tracking | Use |
|---|---|---|---|---|---|
| `{typography.display-hero}` | clamp(22–28px) | 800 | 1.22 | -0.03em | Hero headline (balance-wrapped) |
| `{typography.heading-lg}` | 16px | 700 | 1.4 | -0.01em | Block/card headers |
| `{typography.stat-xl}` | 24px | 700 | 1.15 | -0.02em | Channel message counts (`tnum`) |
| `{typography.body-md}` | 13.5px | 400 | 1.55 | 0 | Default body |
| `{typography.body-card}` | 13.5px | 500 | 1.55 | 0 | Card message text |
| `{typography.caption-md}` | 12px | 400 | 1.5 | 0 | Hero sub, helper text |
| `{typography.label-sm}` | 11px | 500 | 1.5 | 0 | Metadata, sources, timestamps (`tnum`) |
| `{typography.badge-sm}` | 11px | 600 | 1.4 | 0 | Group badges |
| `{typography.button-md}` | 13px | 600 | 1.0 | -0.01em | Button labels |

### Principles
- **Weight does the hierarchy.** 800 → 700 → 500 → 400; at most 4 weights in view at once.
- **Negative tracking only on display tiers.** -0.03em at hero scale; body tracking stays 0.
- **Tabular figures everywhere numbers appear** — counts, times, percentages, the stat ring. This is the system's quiet data signal.
- **`text-wrap: balance`** on the hero headline so CJK/Latin mixed lines break evenly.

## Layout

### Spacing System
- **Base unit**: 8pt grid with 4px sub-token. Tokens `{spacing.xs}` 4px → `{spacing.xxxl}` 32px.
- **Card internal padding**: 12–20px (dashboard density); hero 24×32px.
- **Section gaps**: 16px; card grids 12px.

### Grid & Container
- Overview: 5-column channel card row (→ 3 columns below 1100px) above a `1fr / 320px` main+rail split that collapses to one column on narrow viewports.
- Message stream: fixed conversation rail + fluid message pane; chatter intervals collapse by default.
- Layout collapses via `clamp()` and grid `auto-fill, minmax(240px, 1fr)` rather than breakpoint stacking.

### Whitespace Philosophy
Dashboard density, not marketing airiness — the hero band is the one generous gesture (24×32 padding, breathing gradient), after which cards tighten to 12–16px rhythm. Chatter is folded away by default: whitespace is reclaimed by triage.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| 0 | Flat on `{colors.bg}` | Page canvas |
| 1 | `0 1px 2px rgba(29,28,26,.05), 0 4px 16px rgba(29,28,26,.06)` | Default card (contact + ambient layers) |
| 2 | `0 4px 8px rgba(29,28,26,.08), 0 12px 32px rgba(29,28,26,.12)` + `-2px` spring lift | Hovered/interactive cards, floating panels |
| 3 | The hero gradient band | The spotlight itself — color-as-depth, not shadow |

Shadows are warm-tinted (rgba of the ink `#1d1c1a`, never pure black on light surfaces). Dark theme swaps to black-based shadows at higher opacity.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.sm}` | 8px | Nested cards, list rows, bars |
| `{rounded.md}` | 12px | All cards, the hero, blocks |
| `{rounded.pill}` | 999px | All buttons, badges, inputs |

One radius per nesting level — never mix 12px and 16px siblings; nested cards step down to 8px.

### Ornament Geometry
Channel dots are 8px circles. The stat ring is an 84px SVG circle with an 8px round-capped stroke that animates `stroke-dasharray` on load with a spring. Hero ornaments (✦ ✧) live only inside the gradient band and twinkle on a 2.4s loop.

## Components

### Buttons
- **`button-primary`** — dark warm ink pill (`#241f1a`, white text, 38px, inset top highlight). The single strongest action per view.
- **`button-secondary`** — outlined surface pill (34px, `{colors.line}` border, brand hover).
- **`button-on-hero`** — white pill with deep-brown text (`#7a3a0a`) on the amber band; pops without adding a new hue.
- All buttons: `active { transform: scale(0.97) }`, brand `:focus-visible` ring, 150ms transitions.

### Cards & Containers
- **`card`** — `{colors.surface}` fill, 1px `{colors.line}` border, `{rounded.md}`, Level-1 shadow.
- **`card-hover`** — same body, Level-2 shadow + `-2px` lift on hover with spring easing.
- **`hero-spotlight`** — the gradient band (see Overview). Exactly one per screen.
- **Message cards** — group badge + source line + 2-line clamped text + timestamp footer; the whole card is the jump-to-source affordance.

### Badges, Tags & Chips
- **`badge-group`** — tonal 10% fill + deep-tone 11px/600 text, `{rounded.pill}`, 2×9px padding. Five semantic variants, dark-theme variants included.
- **Channel dots** — the identity of the message's origin; never words when a dot will do.

### Signature Components
- **今日聚光 hero** — 4-stop amber gradient with layered glows, twinkling ✦ ornaments, white 800 display, white CTA. The brand's single unmistakable gesture.
- **Stagger fade-up** — every list (`channel row`, message cards, confirm queue, quick actions, favorites) enters at 0.45s ease-out with 0.05s-per-item delays.
- **Inbound-message ripple** — a 1s box-shadow pulse ring (amber, two repeats) on the inject button when a new message lands.
- **Mascot 小聚** — an emoji mood face (idle 🕊️ / working ⚙️ / waiting 🙋 / happy 🎉 / error 💥) that reacts to agent state; personality without illustration overhead.
- **Approval modal** — the HITL gate rendered as a calm card: risk label, tool args, approve/deny pills, mask-click denies ("宁拦勿纵").

### Inputs
- **`text-input`** — surface pill, `{colors.line}` border, brand focus state, 13.5px body type.

## Do's and Don'ts

### Do
- Keep exactly one hero gradient band and one dark-ink primary button per screen.
- Use tabular numerals on every numeric cell, and `text-wrap: balance` on hero headlines.
- Build depth with the two-layer warm shadows; deepen one level on hover with the spring lift.
- Derive all colors from the token layer so dark mode flips for free.
- Animate entrances with the shared stagger; keep durations at 150/250ms and springs under 0.5s.
- Reserve brand orange for focus, emphasis, and hot states — amber is a spotlight, not wallpaper.

### Don't
- Don't use brand orange for body text or large fills on light surfaces — it fails contrast and cheapens the accent.
- Don't introduce a second gradient family or rainbow accents; the amber band is the only gradient.
- Don't drop the focus ring or shrink touch targets below 34px (44px on mobile).
- Don't exceed four font weights or add tracking to CJK body text.
- Don't stack more than two shadow levels, and never pure-black shadows on light surfaces.
- Don't let badges out-shout the hero — group badges stay tonal and quiet.

## Responsive Behavior

| Width | Key Changes |
|---|---|
| ≥ 1100px | Full layout: 5-col channel row, 1fr/320px main+rail |
| < 1100px | Channel row → 3 col; main+rail collapse to single column |
| Narrow / mobile | Hero text scales via `clamp()`; cards reflow via `auto-fill, minmax(240px, 1fr)` |

Type uses `clamp()` rather than breakpoint steps; buttons keep 34–38px height (44px minimum on touch). The hero gradient re-wraps, never disappears.

## Accessibility & Motion

- `:focus-visible` gets a 2px brand ring with 2px offset on every interactive element.
- Group badge pairs meet 4.5:1 text contrast at 11px.
- `prefers-reduced-motion: reduce` collapses all animation and transition durations to ~0ms — the system degrades to its static form gracefully.
- `::selection` uses the amber-weak/brand-strong pair so even text selection stays on-brand.

## Iteration Guide

1. Change tokens in `web/src/style.css` `:root` first — never hard-code hex in components.
2. Reference tokens by name (`{colors.brand}`, `{rounded.md}`) in reviews and issues.
3. One component at a time; verify states: default / hover / active / focus / disabled.
4. Check the dark-theme variant after any color change (`[data-theme="dark"]`).
5. Run the app (`focusin/start.bat` → http://localhost:5180) and eyeball the 纵览 hero before merging anything visual.
6. New semantic colors enter as a tonal pair (fill + deep text), never a lone hue.
