# Changelog

## Unreleased — Minecraft themes

- Redesign the Grass footer as a compact inventory bar with matching dark controls, keeping its status row and 24px buttons aligned with the other Minecraft themes.
- Align resource slots across all themes and use cyan diamond credits and green emerald tokens.

- Added an original Minecraft-inspired grass-block theme, stone controls, inventory panels, and a matching app icon while preserving window sizes, settings, and query process cleanup.
- Bundled Monocraft/Galmuri9 pixel fonts for all HUD text and Korean notices, added text shadows, XP-style quota bars, inventory item slots, and game-style tooltips.
- Added optional Enchanting Table and End Portal themes; the existing theme button cycles Grass → Enchanting Table → End Portal without changing window sizes or usage retrieval.

- v1.5.0: Fixed refresh-related process accumulation by cleaning up query process trees on completion, errors, timeouts, and app exit.

## v1.5.0 — macOS

- Separate native packages for Apple Silicon and Intel Macs
- Codex path discovery for Finder launches, macOS settings path, and native fonts
- Platform-specific Windows process flags
- Architecture-specific UI, package, signature, and launch checks on macOS runners
- Apple Developer ID signing, notarization, and live account retrieval on macOS remain unverified

## v1.5.0 — Windows / First GitHub release

- Double-click to switch between used and remaining quota in normal and minimal modes
- Per-quota display preferences shared by both layouts
- Used quota fills from the left; remaining quota fills from the right
- Check mark for fully available quota and lock icon for exhausted quota
- Weekly quota by default with an optional five-hour panel
- Light and dark themes with threshold warning colors
- Windows x64 packaged application
