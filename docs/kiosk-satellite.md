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
- **Tablet announcement** (script): call it from any automation with a title and message to show a banner with a chime; add `speak: true` to read it out (needs a text-to-speech engine, e.g. Piper). Skipped when nobody is home or in quiet hours unless you pass `force: true`. Kiosk Satellite's notification action needs every field, even empty ones — the script sends them all.
- **Camera photo when the alarm goes off:** turn on the tablet camera in Kiosk Satellite first; the photo goes to your phones as a time-sensitive notification, and a copy can be kept in a media folder.
- **Clean the screen** (script): lockdown mode for a minute; seven fast taps still exit early.

Example call from an automation:

```yaml
- action: script.tablet_announcement   # the name you gave the script
  data:
    title: Washing machine
    message: The laundry is done.
    icon: mdi:washing-machine
    speak: true
```

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
