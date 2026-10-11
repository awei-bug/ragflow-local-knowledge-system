---
name: RAGFlow
description: Dense local RAG + memory console with quiet surfaces and teal action accents
colors:
  accent-primary: "rgb(0, 190, 180)"
  ink: "rgb(22, 22, 24)"
  paper: "#ffffff"
  canvas: "rgb(246, 246, 247)"
  text-primary: "rgb(22, 22, 24)"
  text-secondary: "rgb(117, 120, 122)"
  text-disabled: "#b2b5b7"
  border-default: "rgba(0, 0, 0, 0.2)"
  border-button: "rgba(0, 0, 0, 0.1)"
  bg-component: "#ffffff"
  bg-input: "rgba(255, 255, 255, 0)"
  bg-card: "rgba(0, 0, 0, 0.05)"
  state-success: "rgb(59, 160, 92)"
  state-warning: "rgb(250, 173, 20)"
  state-error: "rgb(216, 73, 75)"
  core-violet: "rgba(127, 105, 255, 1)"
  dark-base: "#161618"
  dark-component: "#202025"
  dark-text-primary: "rgb(246, 246, 247)"
  dark-text-secondary: "rgb(178, 181, 183)"
typography:
  display:
    fontFamily: "InterVariable, Inter, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  headline:
    fontFamily: "InterVariable, Inter, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "InterVariable, Inter, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "InterVariable, Inter, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "InterVariable, Inter, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "5px"
  DEFAULT: "6px"
  md: "7px"
  lg: "8px"
  xl: "8px"
  "2xl": "10px"
  "3xl": "12px"
  "4xl": "16px"
  full: "9999px"
spacing:
  "0.5": "2px"
  "1": "4px"
  "1.5": "6px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "6": "24px"
  "8": "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.DEFAULT}"
    padding: "0 12px"
    height: "32px"
    typography: "{typography.body}"
  button-accent:
    backgroundColor: "{colors.accent-primary}"
    textColor: "#ffffff"
    rounded: "{rounded.DEFAULT}"
    padding: "0 12px"
    height: "32px"
  button-outline:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.DEFAULT}"
    padding: "0 12px"
    height: "32px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.DEFAULT}"
    padding: "0 12px"
    height: "32px"
  button-danger:
    backgroundColor: "transparent"
    textColor: "{colors.state-error}"
    rounded: "{rounded.DEFAULT}"
    padding: "0 12px"
    height: "32px"
  input-default:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "32px"
    typography: "{typography.body}"
  card-default:
    backgroundColor: "{colors.bg-input}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "24px"
  badge-secondary:
    backgroundColor: "{colors.bg-card}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.DEFAULT}"
    padding: "2px 10px"
    typography: "{typography.label}"
  badge-success:
    backgroundColor: "rgba(59, 160, 92, 0.05)"
    textColor: "{colors.state-success}"
    rounded: "{rounded.DEFAULT}"
    padding: "2px 10px"
  badge-error:
    backgroundColor: "rgba(216, 73, 75, 0.05)"
    textColor: "{colors.state-error}"
    rounded: "{rounded.DEFAULT}"
    padding: "2px 10px"
  button-primary-hover:
    backgroundColor: "rgba(22, 22, 24, 0.9)"
    textColor: "{colors.paper}"
  sidebar-shell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.text-primary}"
    width: "16rem"
---


# Design System: RAGFlow

## Overview

**Creative North Star: "The Local Context Console"**

RAGFlow is an operate-first product UI for local RAG, agent workflows, and durable memory. The visual system favors dense, scannable tool surfaces over marketing expression. Screens are full-viewport app shells with sidebars, filter bars, tables, forms, and chat/memory workspaces.

Surfaces stay quiet: near-white or near-black bases, thin hairline borders, restrained shadows, and compact 32px controls. Action color is used sparingly. Teal marks confirmation, focus, and product-critical action; ink fills primary commands; violet remains a secondary sentiment accent from older token layers, not the main brand voice.

Chinese-first operational copy coexists with English engineering terms (RAG, Agent, Memory, Dataset). Hierarchy is utilitarian: short page titles, dense body text, and status chips that resolve state at a glance.

**Key Characteristics:**
- Full-viewport app shell (`100dvw` / `100dvh`, overflow hidden)
- Compact control density (default control height 32px)
- Hairline borders (`0.5px`) and tonal layering instead of heavy chrome
- Teal accent for focus/action; ink for primary solid buttons
- Inter / InterVariable as the single UI type family
- Light and dark modes share the same structure with inverted neutrals

## Colors

The palette is a quiet neutral console with one operational teal accent and functional state colors.

### Primary
- **Operational Teal** (`rgb(0, 190, 180)` / `--accent-primary`): Focus rings, accent buttons, highlight marks, and product-critical action moments. Keep rare so it remains legible as signal.

### Secondary
- **Core Violet** (`rgba(127, 105, 255, 1)` / `--colors-text-core-standard`): Legacy sentiment/outline accent. Use only where existing violet token surfaces still appear; do not expand it as a second brand system.

### Neutral
- **Ink** (`rgb(22, 22, 24)`): Primary text and solid default buttons in light mode.
- **Paper** (`#ffffff` / `--bg-base`): Main app surface in light mode.
- **Canvas Mist** (`rgb(246, 246, 247)` / `--bg-canvas`, `--bg-list`): List wells, page gutters, and soft canvas behind cards.
- **Secondary Graphite** (`rgb(117, 120, 122)`): Secondary labels, muted button text, helper copy.
- **Disabled Mist** (`#b2b5b7`): Placeholder and disabled text.
- **Hairline Border** (`rgba(0,0,0,0.2)` default / `rgba(0,0,0,0.1)` button): Structural edges for inputs, cards, and controls.
- **Dark Base** (`#161618`) / **Dark Component** (`#202025`): Dark-mode app and elevated component surfaces.

### Functional
- **Success** (`rgb(59, 160, 92)`), **Warning** (`rgb(250, 173, 20)`), **Error** (`rgb(216, 73, 75)`): Status chips, destructive actions, validation.

**The One Accent Rule.** Teal is the only frequent brand action color. Do not invent extra brand hues for new screens.

**The Operational Token Prefer Rule.** Prefer `--bg-*`, `--text-*`, `--accent-primary`, `--border-*`, and `--state-*` over older shadcn HSL or violet core tokens when both exist.

## Typography

**Display Font:** InterVariable / Inter (system-ui fallback)
**Body Font:** InterVariable / Inter
**Label/Mono Font:** Inter for labels; no dedicated mono brand face in the current system

**Character:** Neutral engineering type. High legibility at dense sizes, no display serif, no decorative tracking.

### Hierarchy
- **Display / H1** (700, `1.5rem` / `text-2xl`): Rare page-level titles and card titles when intentionally large.
- **Headline / H2** (600, `1.25rem` / `text-xl`): Section heads in settings and multi-panel pages.
- **Title / H3** (500, `1.125rem` / `text-lg`): Panel and group titles.
- **Body / H4 + controls** (400-500, `0.875rem`-`1rem`): Default UI copy, table cells, form labels, buttons (`text-sm` on controls).
- **Label / Badge** (600, `0.75rem` / `text-xs`): Status chips and compact metadata.

**The Dense Type Rule.** Prefer `text-sm` for interactive controls and operational content. Reserve larger type for true page structure, not every card heading.

## Layout

The product is a full-viewport application, not a scrollable marketing site. `html`, `body`, and `#root` lock to `100dvw` / `100dvh` with `overflow: hidden`; individual panels scroll internally.

- **App shell:** Persistent sidebar + main content. Expanded sidebar `16rem`, icon-collapsed `3rem`, mobile sheet `18rem`.
- **Legacy layout vars still present:** header `64px`, older menu width `200px` / compact `83px`.
- **Density:** Compact tool rhythm. Default control height is 32px; common paddings are 8 / 12 / 16 / 24px.
- **Breakpoints:** `sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`, `3xl 1780`, `4xl 1980`.
- **Container:** Centered container with `2rem` padding; `2xl` screen cap at `1536px` for constrained content, while app shells often span full width.
- **Structure pattern:** Filter/tool bars above tables or message lists; settings as stacked forms; memory/chat as multi-panel workspaces.

**The Internal Scroll Rule.** Scroll inside panels and tables, not the whole app frame.

## Elevation & Depth

Depth is mostly tonal and bordered, not theatrical. Cards and controls sit on quiet surfaces with hairline borders; shadows are light and optional.

### Shadow Vocabulary
- **Control whisper** (`shadow-xs` on solid/default and destructive buttons): Barely lifted primary actions.
- **Card rest** (`shadow-sm` on cards): Soft separation from canvas without floating chrome.
- **No heavy elevation stack:** Avoid multi-level drop-shadow hierarchies, glassmorphism, or decorative orbs.

**The Flat-By-Default Rule.** Surfaces are flat at rest. Borders and background shifts define structure; shadows only lightly reinforce interactive or card boundaries.

## Shapes

Corners are gently rounded and intentionally small for a dense console.

- Default control radius is about 6px (`rounded` / `0.375rem`).
- Inputs commonly use ~7px (`rounded-md`).
- Cards use ~7-8px (`rounded-lg`) with `border-0.5`.
- Compact sizes step down to 4-5px; larger controls step up to 8-12px.
- Badges are often pill (`rounded-full`) or soft chip (`rounded-md`).
- Borders are characteristically thin: `0.5px` is a product signature.

**The Hairline Edge Rule.** Prefer `border-0.5` + quiet fill over thick outlines or oversized rounded cards.

## Components

### Buttons
- **Shape:** Compact rounded rectangle (~6px), default height 32px, horizontal padding 12px, `text-sm`.
- **Primary (default):** Ink fill (`bg-text-primary`) on paper text (`text-bg-base`); light `shadow-xs`.
- **Accent:** Teal fill with white text for high-signal actions.
- **Secondary / Outline / Transparent:** Quiet fills or transparent bodies with `border-button`; text starts secondary and strengthens on hover.
- **Ghost / Delete:** No border; hover uses border-button wash or soft error wash.
- **Danger / Destructive:** Error outline or solid error fill; never style destructive actions as teal.
- **Highlighted:** Ink fill with a teal bottom edge accent.
- **Sizes:** `xl 48`, `lg 40`, `default 32`, `sm 28`, `xs 24`, plus matching icon sizes.

### Chips / Badges
- **Style:** Compact status markers, usually `text-xs font-semibold`.
- **Secondary:** Soft card wash + secondary text.
- **Success / Error:** 5% state wash + solid state text.
- **Use for:** memory states, parse states, model/config tags-not as primary navigation.

### Cards / Containers
- **Corner Style:** Gently rounded (~7-8px)
- **Background:** `bg-bg-input` / component surface
- **Border:** `border-0.5 border-border-button`
- **Shadow Strategy:** Light `shadow-sm`
- **Internal Padding:** Commonly `p-6` in primitive card, but denser product pages often tighten this

### Inputs / Fields
- **Style:** Height 32px, `rounded-md`, hairline `border-border-button`, transparent/light input wash, `text-sm`
- **Focus:** `ring-1 ring-accent-primary` (teal), no thick blue browser glow
- **Placeholder:** `text-text-disabled`
- **Affordance:** Search prefix icon and password reveal are first-class patterns

### Navigation
- **Sidebar shell:** 16rem expanded / 3rem icon rail / 18rem mobile sheet
- **Behavior:** Cookie-persisted open state; keyboard shortcut `b`
- **Style:** Quiet list of destinations; active states rely on sidebar tokens and compact buttons/tooltips rather than large marketing nav

### Signature Patterns
- **App shell workspaces:** sidebar + filter bar + table/list + detail/settings
- **Memory surfaces:** list/message tables and settings forms should reuse the same compact control language, not invent a separate visual world
- **Highlight marks in document views:** teal wash at low alpha for selected/scrolled highlights

## Do's and Don'ts

### Do:
- **Do** design for Operate mode: dense, scannable, bilingual operational UI.
- **Do** use teal only for focus, accent actions, and true highlights.
- **Do** keep default controls at 32px with hairline borders and small radii.
- **Do** prefer operational tokens (`bg-base`, `text-primary`, `accent-primary`, `border-button`, state colors).
- **Do** scroll inside panels; keep the outer app shell fixed.
- **Do** support light and dark with the same structure and inverted neutrals.

### Don't:
- **Don't** turn product pages into marketing heroes, oversized cards, or gradient orb backgrounds.
- **Don't** introduce a second brand palette (no new purple-first or blue-first redesigns for ordinary screens).
- **Don't** use thick borders, large 16px+ radii on routine controls, or heavy multi-shadow stacks.
- **Don't** rely on temporary chat chrome as the memory metaphor; memory UI should feel like durable knowledge operations.
- **Don't** invent customer logos, fake benchmarks, or unverified brand claims in UI.
- **Don't** treat older Ant blue (`#338AFF`) or violet core tokens as the primary redesign target unless explicitly refreshing legacy surfaces.
