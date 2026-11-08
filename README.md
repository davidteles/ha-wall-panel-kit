# Wall Panel Kit for Home Assistant

A **wall-tablet dashboard** and a matching **phone dashboard**, generated from one short file that lists your rooms and entities. Frosted-glass look, an "attention" strip that only shows what needs doing, one tap to every room — and on phones, a floating bottom tab bar with **no kiosk mode, ever**.

```
my_home.yaml  ──►  python tools/render.py  ──►  out/tablet.yaml   (wall tablet)
                                             └─►  out/phone.yaml    (iPhone / Android)
```

## What you get

| Page | Tablet | Phone |
|---|---|---|
| **Home** | Clock + weather, attention strip, "N lights on — tap to turn all off", alarm, people, rooms, calendar | Same cards, no big clock, 3-day forecast |
| **Rooms** | One tile per room, with its temperature | Same |
| **Each room** | Temperature, humidity, lights (with brightness), climate, blinds, media, extras | Same, one column |
| **Security** | Alarm with arm/disarm modes (if you have an alarm) | Same |
| **Energy** | Live power gauge, today's energy, energy distribution (if configured) | Same |
| **Frame** | Optional kiosk mode on touch tablets only, optional photo screensaver | Bottom tab bar, ← back on every page, never kiosk |

The attention strip lists open doors/windows, batteries under 15 % and lights left on with nobody home — and stays empty the rest of the time.

## Requirements

Home Assistant 2025.1 or newer, plus these frontend cards from HACS:

| Card | Used for | Needed by |
|---|---|---|
| [Mushroom](https://github.com/piitaya/lovelace-mushroom) | Lights summary, room tiles | Both |
| [card-mod](https://github.com/thomasloven/lovelace-card-mod) | Attention strip accent | Both (optional) |
| [Clock Weather Card](https://github.com/pkissling/clock-weather-card) | Clock and forecast | Both |
| [navbar-card](https://github.com/joseluis9595/lovelace-navbar-card) | Bottom tab bar | Phone |
| [kiosk-mode](https://github.com/NemesisRE/kiosk-mode) | Hide header/sidebar on the tablet | Tablet, if `kiosk: true` |
| [Wall Panel](https://github.com/j-a-n/lovelace-wallpanel) | Photo screensaver | Tablet, if `screensaver` is set |

## Quick start

1. **Get the kit** — download this repository (Code → Download ZIP) or `git clone` it.
2. **Describe your home** — copy `my_home.example.yaml` to `my_home.yaml` and fill in your entity ids. Find them in Settings → Devices & services → Entities. Remove any optional line you don't need.
3. **Build** (Python 3.10+):
   ```bash
   pip install -r tools/requirements.txt
   python tools/render.py
   ```
4. **Create the dashboards** in Home Assistant: Settings → Dashboards → **Add dashboard** → *New dashboard from scratch*.
   - Name the tablet one **Wall Panel** with the URL `wall-panel`, and the phone one **Phone** with `phone-home` (the tab bar and back arrows use these URLs).
   - Open each one → ✏️ → ⋮ → **Raw configuration editor**, replace everything with the contents of `out/tablet.yaml` or `out/phone.yaml`, and save.
5. **Add the theme** — copy `themes/wall-panel.yaml` into your `themes` folder ([how](https://www.home-assistant.io/integrations/frontend/#defining-themes)), reload themes and pick **Wall Panel** in your profile, or on the tablet only.
6. **On each phone**, choose the Phone dashboard in the companion app: Profile → Dashboard.

Change `my_home.yaml` and run the script again whenever you add a room or device. The output is plain YAML, so you can also keep editing in the dashboard editor — but then re-running the script overwrites your edits.

## `my_home.yaml` reference

```yaml
title: Home
weather: weather.home
calendar: calendar.family            # optional
alarm: alarm_control_panel.home      # optional → adds Security
people: [person.alex, person.sam]    # optional

tablet:
  kiosk: true                        # hide header + sidebar on touch tablets
  admin_toggle: input_boolean.wall_panel_admin_mode   # optional, header returns while on
  screensaver:                       # optional
    idle_seconds: 180
    photos: media-source://media_source/local/wallpanel

energy:                              # optional → adds Energy
  power_now: sensor.home_power
  energy_today: sensor.home_energy_today

rooms:
  - name: Living room
    icon: mdi:sofa
    temperature: sensor.living_room_temperature
    humidity: sensor.living_room_humidity
    lights: [light.ceiling, light.sofa_lamp]
    climate: climate.living_room
    media: media_player.living_room
    covers: [cover.living_room_blinds]
    other: [switch.coffee_machine]
```

Room names must be unique and can't be *Home*, *Rooms*, *Security* or *Energy*.

> **Admin toggle:** create it under Settings → Devices & services → Helpers → *Toggle*. Turn it on from another device when you need the header on the tablet to edit.

## Design

The rules behind the layout — what goes on Home, why phones never get kiosk mode, how colour is used, which actions ask for confirmation — are in [docs/design.md](docs/design.md).

## Roadmap

- **Phase 1 (now):** generator for tablet + phone from `my_home.yaml`.
- **Phase 2:** a dashboard *strategy* that builds the same layout straight from your Home Assistant areas — no file, no script.
- More pages: car, media, shopping list, a guest view, seasonal extras (see [ha-festive-panel](https://github.com/davidteles/ha-festive-panel)).

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
