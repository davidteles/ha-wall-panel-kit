# Kiosk Satellite tablets

Extras for a wall tablet running [Kiosk Satellite](https://kiosksatellite.com) with its Home Assistant (ESPHome) integration. They use the tablet's own features (hold mode, screensaver schedule, kiosk mode, overlays) instead of browser add-ons.

## Helpers to create first (Settings → Devices & services → Helpers)

| Helper | Type | Options / notes | Used by |
|---|---|---|---|
| Tablet held by automation | Toggle | — | Keep awake |
| Kiosk mode policy | Dropdown | `Auto`, `Always on`, `Always off` | Kiosk mode policy |
| Screensaver style | Dropdown | `Auto`, `No photos`, `Photos day and night`, `Screen off` | Screensaver style |
| Panel settings unlocked | Toggle | Optional: shows the settings only while on | Settings page |

## Blueprints

- **Keep the tablet awake while it matters:** the screen stays on while the alarm counts down, a Leaving timer runs or the voice assistant talks; it lets go 20 s later, only if it held it.
- **Keep a countdown visible over Now Playing:** closes the full-screen player while a countdown runs, so *Cancel* stays reachable.
- **Kiosk mode policy:** a dropdown decides kiosk mode — Always on, Always off, or Auto (back on by itself a few minutes after someone leaves it).
- **Screensaver style, away and guest mode:** one dropdown for the screensaver; black and off when nobody is home; clock only (no family photos) while the guest page is open.

Import buttons are in the main README.

## A "Panel settings" page

A sub-view you open from the Security page (or anywhere behind a PIN). Example:

```yaml
title: Panel settings
path: panel-settings
subview: true
type: sections
sections:
  - type: grid
    cards:
      - type: heading
        heading: Panel
      - type: tile
        entity: input_select.screensaver_style
        features: [{ type: select-options }]
        grid_options: { columns: 12 }
      - type: tile
        entity: input_select.kiosk_mode_policy
        features: [{ type: select-options }]
        grid_options: { columns: 12 }
      - type: tile
        entity: switch.my_tablet_kiosk_mode
        name: Kiosk mode now
        grid_options: { columns: 12 }
      - type: tile
        entity: switch.my_tablet_lockdown_mode
        name: Clean screen (touch off)
        grid_options: { columns: 12 }
```

Replace `switch.my_tablet_…` with your tablet's entities. Put `visibility` conditions on the cards (e.g. a *Panel settings unlocked* toggle) if the page shouldn't be open to everyone.
