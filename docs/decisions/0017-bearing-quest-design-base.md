# 0017. Adopt the Bearing Quest design base

- **Status:** Accepted
- **Date:** 2026-10-29

## Context
On 29 Oct 2026 the owner decided that every GUI app in his projects uses the
Bearing Quest design system as a shared base, so they share one look. Risk
Trainer is excluded. Bearing Quest is a project-family name, never a company.

The design system is kept as a claude.ai artifact. It holds the tokens
(`tokens.json`) and the logo SVGs, and it is the source of truth for both.
This record states the rules QuestVector takes from it.

On 16 Oct 2026 the owner decided to keep QuestVector's "Tactical Ops Flight
Deck" look and to share conventions with risk-trainer, not its visual design
(backlog item 15). That decision was never written up as an ADR. This record
updates it and does not supersede it: the Flight Deck instrument-panel motif
stays, now on the shared base.

The current interface (`questvector/desktop/web/` on `main`, checked 29 Oct
2026) has no focus styles and no light/dark handling, so the base adds
these rather than replacing them.

## Decision
QuestVector's desktop app and browser app (ADR-0016) use the Bearing Quest
base and keep the Flight Deck instrument-panel motif. QuestVector's own
accent color is still to be chosen.

- **Color tokens, light and dark:**

  | Token | Light | Dark |
  |---|---|---|
  | Brand (navy) | `#1B365D` | `#1B365D` |
  | UI accent | `#B4501F` | `#E8894F` |
  | Text | `#3A3D40` | `#F4F6F8` |
  | Ground | `#F4F6F8` | `#10213A` |
  | Surface | `#FFFFFF` | `#1B365D` |
  | Control outline | `#7A8594` | `#8EA0B5` |
  | Focus | `#1B365D` | `#F0A06B` |
  | Error | `#B42318` | `#FF8A80` |

  They are generated into CSS custom properties from the design system's
  `tokens.json`, never pasted into stylesheets as hex.
- **Fonts:** Inter for UI and body text, IBM Plex Mono for IDs, figures and
  code, and Cinzel for the wordmark only. All three are under the SIL Open
  Font License 1.1. They are self-hosted from pinned releases, checked
  against hashes, with each font's OFL file shipped beside it. No font CDN,
  in line with ADR-0016's self-hosted pinned assets and strict CSP.
  - Cinzel is vendored only if the app sets the wordmark as live text. The
    design system's lockup SVG already has the wordmark as outlines, so
    using the SVG needs no Cinzel file.
- **Accent orange** is for links and at most one call to action per screen.
  It is never used on match scores or other data. Data gets its own
  lightness-ordered, colorblind-safe scale, with a number or word beside
  every color.
- **Logo:** the Bearing Quest SVGs from the design system, not redrawn.
- **Contrast test:** a test checks the tokens in both themes against WCAG
  2.2 AA, with 3:1 for focus rings and control outlines.

## Consequences
- **Font files and licences to vendor:** Inter and IBM Plex Mono, plus
  Cinzel only if the wordmark is set as live text, each with its OFL file,
  pinned and hash-checked like the browser app's other assets.
- **The browser app's CSP needs `font-src 'self'`.** No new network path, so
  ADR-0001 is unaffected.
- **Exports:** PDF export embeds Inter. DOCX names Inter with a system
  fallback, since a DOCX can't rely on the font being installed.
- **The contrast test is added with the first UI pull request,** together
  with the generated CSS custom properties.
- **One stylesheet** serves the pywebview window and the browser app.
- **Still open:** QuestVector's accent color, to be chosen and
  contrast-checked in both themes before UI code; and whether labels are
  themed, plain, or both (backlog item 15).
