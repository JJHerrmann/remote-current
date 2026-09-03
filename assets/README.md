# Site assets

Derived from the source artwork in the repo root:

- `remote_current_favicon.ico` — multi-resolution icon (16–256px).
- `remote_current_favicon_transparent.png` — 1065² "RC/" mark, off-white
  glyph + orange slash, transparent background.

Generated files (regenerate with Pillow if the source changes):

| File | What | How |
|------|------|-----|
| `../favicon.ico` | tab icon, all pages | copy of `remote_current_favicon.ico` |
| `logo-dark.png` | masthead mark on dark themes | source, glyph recoloured to `#e9e6de`, trimmed, 128px tall |
| `logo-light.png` | masthead mark on light themes | source, glyph recoloured to `#1b1e20`, trimmed, 128px tall |
| `apple-touch-icon.png` | iOS home-screen icon | mark centred on an opaque `#1b1e20` 180² square |
| `og-image.jpg` | Open Graph / Twitter share card, 1200×630 (~81 KB) | downscaled and re-encoded from `og-image2.png`, the full-size source card |

The masthead swaps `logo-light` / `logo-dark` by theme in CSS (`.wordmark .logo`).
The orange slash keeps its colour in both variants; only the "RC" glyph is
recoloured.
