# QuestVector design

The reference for building QuestVector's interface on the Bearing Quest design base ([ADR-0017](decisions/0017-bearing-quest-design-base.md)). It applies to the desktop (pywebview) window and the browser app ([ADR-0016](decisions/0016-browser-app-static-pages.md)), which share one stylesheet. Bearing Quest is a project-family name, never a company.

Snapshot taken 29 Oct 2026 from the Bearing Quest design system (a private claude.ai artifact). When the two differ, this repo's copy is what the code uses; changes to it come in through a pull request like any other file.

## What's in `docs/design/`

| Path | What it is | How to use it |
|---|---|---|
| `tokens.json` | Every shared token: colors for light and dark (including `qv-accent`, `on-qv-accent`, `caution` and `caution-bg`), type styles, spacing, radius and shadow, each with a usage note and its contrast ratios | Generate the CSS custom properties from it. Don't paste hex values into stylesheets |
| `logo/bearing-quest-mark-on-light.svg`, `-on-dark.svg` | Full-colour compass mark | The header mark beside the QuestVector name (36 px). Pick the file for the theme |
| `logo/bearing-quest-mark-mono-navy.svg`, `-mono-white.svg` | Single-colour mark | Favicons and watermarks |
| `logo/bearing-quest-lockup-on-light.svg`, `-on-dark.svg` | Mark plus the BEARING QUEST wordmark as outlines (no font needed) | Only where the family name itself is shown, such as an About page |
| `mockups/*.png` | The five accepted screens, 1280 px wide: match (light and dark), workspace, key vault, export | The visual target for the first UI pull requests |
| `mockup-reference.css` | The stylesheet the mockups were drawn with | A reference for layout and component values, not production CSS. Token values in it match `tokens.json`; `--track` is the `border` value |

Use the logo files through `<img>` or as CSS backgrounds. Their mask ids (`m`, `h`, `bq-lm`, `bq-lh`) would collide if two were inlined in one page.

## QuestVector's layer on the shared base

- **Motif:** the Flight Deck instrument panel. Readouts in `figure` and `id` styles, a gauge for the match score with the number and status word beside it, tick marks under the category bars.
- **Accent:** Horizon blue, `qv-accent` (#1F68A8 light, #7DB8F0 dark), with `on-qv-accent` for text on it. It marks the active tab, the selected mission template, the gauge and the category bars. Links and the single call to action per screen stay `accent` (orange).
- **Labels:** themed (Sync-AST, G-Force, Vault, mission template), decided 29 Oct 2026.
- **Header:** the Bearing Quest mark beside the QuestVector name shows the family. No separate family strip (decided 29 Oct 2026; Risk Trainer uses a strip because it keeps its own Blueprint colours).
- **Match status:** always a word and an icon.

  | Status | `AlertLevel` (core/models.py) | Treatment |
  |---|---|---|
  | Locked | `SUCCESS` | `heading` color, outlined |
  | Gaps | `WARNING` | `caution` on `caution-bg` (decided 29 Oct 2026) |
  | Critical | `CRITICAL` | `error` on `error-bg` |

  The level itself comes from `core/matcher.py` and doesn't change. No red/green pair, and color is never the only signal. The HUD colors in `config.py` (Tactical Green, Afterburner Amber, Lock-On Red) and the current `desktop/web/` CSS are replaced by these tokens in the first UI pull request.

## Rules from the shared base

- Fonts: Inter for UI and body, IBM Plex Mono for IDs, figures and code. Self-host pinned releases with SHA-256 hashes and ship each OFL licence beside the files; no font CDN. Cinzel isn't needed, since the lockup SVGs have the wordmark as outlines.
- Data colors never use `accent` or `error`.
- Focus: 2px solid `focus` ring with a 2px offset on every focusable element, both themes.
- Contrast: an automated test checks the token pairs named in `tokens.json` in both themes against WCAG 2.2 AA (4.5:1 text; 3:1 focus rings, control outlines and bar fills against their track).
- Themes: light, dark and auto (follows the device), with a manual switch in settings.
- Copy: plain words, sentence case, "you", no absolutes about security controls, sample data labelled as synthetic.

## Still open

- Plain-word help text for each themed term (for example, what G-Force measures). Recommended, not decided.
- Font provenance for the first UI pull request: Risk Trainer's 29 Oct 2026 approach (official Inter v4.1 release, subset with pinned fonttools, hashes pinned in a test) is a working example to reuse.
