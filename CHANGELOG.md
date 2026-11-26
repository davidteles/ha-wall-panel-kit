# Changelog

All notable changes to this project. Versions follow [semantic versioning](https://semver.org/); each entry links to its full release notes on GitHub, which also say how each change was tested.

## [1.12.0] — 2026-11-26

Attention strip skips thermostats and cars.

- **Attention strip: skip doors/windows of thermostats and cars** ([#29](https://github.com/davidteles/ha-wall-panel-kit/pull/29)).

_Upgrading:_ regenerate your dashboards. Thermostat and car sensors drop off the strip by default; set `skip_climate_devices: false` to keep them.

## [1.11.0] — 2026-11-26

Match strip: several competitions ([#28](https://github.com/davidteles/ha-wall-panel-kit/pull/28)).

_Upgrading:_ nothing to do with one competition. If you used the "all" league, follow "Several competitions" in docs/match.md.

## [1.10.0] — 2026-11-24

Your team's match on Home (Team Tracker).

- **Your team's match on Home** ([#27](https://github.com/davidteles/ha-wall-panel-kit/pull/27)). New optional `match:` block for the [Team Tracker](https://github.com/vasqued2/ha-teamtracker) integration.
- **A slim strip under the clock and weather** while your match window is on, from 30 minutes before kick-off until an hour after the final whistle.
- **GOAL line:** for 5 minutes after a goal, "⚽ GOAL <team>!" goes first in the attention strip, and the strip says "⚽ GOAL!".
- **It fits:** 56 px tall, the same as the other alert cards, and gone outside the match.
- **One rule:** the window and the goal alert are two template helpers (docs/match.md). Point anything else (a screensaver line, a second card) at the same helpers.
- **Restart-safe:** the end time comes from a helper filled by the new *Team Tracker match memory* blueprint in [ha-blueprints v1.15.0](https://github.com/davidteles/ha-blueprints/releases/tag/v1.15.0), never from `last_changed`.
- **Checks:** validation names each bad key; `goal_alert` and `goal_by` go together.
- **Setup:** see [docs/match.md](https://github.com/davidteles/ha-wall-panel-kit/blob/main/docs/match.md). It covers the 3 helpers, the blueprint, the 2 template helpers and the `match:` block.

_Upgrading:_ nothing to do. Without a `match:` block the output is unchanged.

## [1.9.2] — 2026-11-23

Start here: choose your setup.

- **Start here: choose your setup** ([#25](https://github.com/davidteles/ha-wall-panel-kit/pull/25)). README only; nothing in the generator, blueprints or dashboards changed.
- **Where to start:** a short chooser at the top of the README.
- **What to leave off at first:** kiosk mode only after the tablet view looks right in a normal browser; no blueprints or helpers for features you haven't turned on.
- **Copy-and-paste first run:** the one-room example, `render.py --needs`, `render.py`.
- **What `--needs` does and doesn't do:** it lists cards and checks entity ids. It doesn't install cards or tell whether they're installed.
- **Links** to import, undo (`out/previous/`) and *Remove it*.

## [1.9.1] — 2026-11-23

Entry: 'opened' only when it really opened.

- **Entry: say only what is known** ([#24](https://github.com/davidteles/ha-wall-panel-kit/pull/24))
- The phones and the tablet pop-up say **opened** only when the door's confirmation sensor *changed* to open after you tapped. A door that was already open, or a lock already unlocked, no longer counts: you get **Open sent** instead.
- A lock only confirms **🔓 unlocked** (the latch is free; the door may still be shut). A gate that's still moving says **opening**.
- **Tablet pop-up:** add `confirm:` to each door in `my_home.yaml` (the same entity as in its *Open a door* script), then run `render.py` again. Without it, the pop-up says *Open sent to …*; before, it said *opened* even when nothing confirmed it.

## [1.9.0] — 2026-11-23

Alarm takeover, --needs setup check, Entry 'opened' only when confirmed.

- **Alarm takeover** ([#21](https://github.com/davidteles/ha-wall-panel-kit/pull/21)): opt-in `alarm_takeover:` covers every tablet and phone page with a red pop-up while the alarm counts down or goes off — what was opened, **"The alarm goes off in …"** and the PIN pad. New **Alarm countdown** blueprint for the timer.
- **`render.py --needs`** ([#22](https://github.com/davidteles/ha-wall-panel-kit/pull/22)): lists the cards for the features you turned on, every entity your file uses, and a template for Developer tools that names any missing entity. Writes nothing.
- **Entry** ([#23](https://github.com/davidteles/ha-wall-panel-kit/pull/23)): the phones say "opened" only when a sensor confirms it (new optional *Confirms it opened* input); otherwise "Open sent".

## [1.8.0] — 2026-11-22

Your own lines in the attention strip.

- **Attention strip: `extra_alerts`** ([#20](https://github.com/davidteles/ha-wall-panel-kit/pull/20)). Add anything only you know matters, e.g. a dehumidifier's tank-full sensor.

## [1.7.1] — 2026-11-19

Laundry: two equal choices with a labelled recommendation.

- **Hung indoors / Hung outside** are the same size.
- **The recommended one** says *Recommended* and has a subtle border, so it doesn't rely on colour alone. With no reliable forecast, neither is highlighted. Nothing is preselected: only a tap confirms.
- **Nothing to hang** becomes a smaller chip and keeps its confirmation.
- **Every laundry button passes `step`** (`hung` / `move`), so a late tap can't overwrite an answer that already came from a phone. This needs **Laundry hung** from [ha-blueprints v1.10.1](https://github.com/davidteles/ha-blueprints/releases/tag/v1.10.1).
- **Docs:** `docs/laundry.md` and its screenshot are updated.

## [1.7.0] — 2026-11-19

Laundry cards: ready to hang, where it's drying, rain.

- **Wash done:** "Laundry ready to hang · outside recommended", with the reason and finish time. Then **Hung indoors / Hung outside / Nothing to hang**, with *Recommended* on one.
- **On the rack, nobody chose:** "where is it drying?" with **Indoors** / **Outside**.
- **Drying:** "Drying outside · tap to change to indoors", with a confirmation.
- **Rain is coming while it's outside:** a red card, "tap when it's indoors".
- **Attention strip:** 🧺 *Laundry ready to hang* and ☔ *Laundry is outside and rain is coming*.
- The buttons have no entity, so tapping an icon does exactly what tapping the card does.
- It works with [ha-blueprints v1.10.0](https://github.com/davidteles/ha-blueprints/releases/tag/v1.10.0)'s laundry blueprints. With only `waiting`, you get one "tap when it's out" card.

## [1.6.0] — 2026-11-19

Entry: doorbell, intercom, door and gate.

- **Pop-up while it rings:** it covers whatever page is open on the tablet and phone dashboards. It shows the live camera, quick replies and one button per door plus *Dismiss*. It needs only card-mod.
- **Entry page** (a tab on the tablet and the phone): camera, last ring, open buttons.
- **Attention strip:** 🔔 *Someone at the building door*.
- **Blueprint "Entry — someone rang"** (automation).
- **Blueprint "Entry — open a door"** (script).
- **Status:** new. Tested in a sample home (Home Assistant 2026.2.3) and by automated scenario tests. It has **not been tested with a real doorbell or intercom yet**; reports are welcome.

## [1.5.2] — 2026-11-18

"1 light on", Leaving sequence, how to remove it.

- **"1 light on"**, not "1 lights on", in the lights tile and in the attention strip ("1 light on and nobody home"). Covered by a new test.
- The Leaving screenshots are now a sequence: before → countdown → **I'm staying** puts every light and speaker back. Taken in a sample home with the kit's own Leaving blueprints.

## [1.5.1] — 2026-11-18

Clock Weather Card v3, no empty boxes, screenshots.

- **Clock Weather Card v3:** v3 removed `forecast_rows`, `time_format` and `hide_clock`, so the generated clock/forecast card fell back to its default layout.
- **No empty boxes:** the attention strip and the welcome-home message no longer leave an empty rounded box when there's nothing to show.
- Screenshots in the README (from a sample home with made-up people): tablet and phone, the attention strip, the Leaving countdown, a room page.
- Requirements now say **Clock Weather Card v3 or newer**.

## [1.5.0] — 2026-11-17

One-room starter, safe regeneration, tested generator.

- **One-room starter** (`examples/one_room.yaml`): a title, a weather entity and one room with one light. Start there and grow it.
- **Safe regeneration:** every run moves the last output to `out/previous/` first, so undoing is one paste. `--out DIR` writes somewhere else, to try things.
- **Clear errors, all at once:** every problem in `my_home.yaml` is listed with where it is (e.g. `rooms[1] (Kitchen) lights[0]: 'kitchen lamp' is not an entity id`), including reserved or duplicate room names and a value where a list is expected.

## [1.4.0] — 2026-11-17

Guest at home on the tablet.

- **Guest at home** (optional switch) for the Kiosk Satellite blueprints.

## [1.3.1] — 2026-11-16

Alarm photo shows on iPhones.

- **Camera photo when the alarm goes off:** the phones now get the saved photo file (press and hold the notification to see it) instead of the live camera link, which iPhones did not always attach.

## [1.3.0] — 2026-11-16

Tablet announcements, alarm photo, clean screen.

- **Tablet announcement** (script): a banner with a chime on the tablet, read out loud if you ask (any TTS engine, language and voice). It stays quiet when nobody is home or during quiet hours, unless called with `force`.
- **Camera photo when the alarm goes off**: the tablet's front camera takes a photo and your phones get it as a time-sensitive notification; a copy can be saved in a media folder.
- **Clean the screen** (script): touch off (lockdown mode) for a minute so you can wipe the screen.

## [1.2.0] — 2026-11-16

Kiosk Satellite tablets.

- **Keep the tablet awake while it matters** — screen held on during the alarm countdown, a Leaving timer or a voice conversation; released afterwards only if it held it.
- **Keep a countdown visible over Now Playing** — closes the full-screen player while a countdown runs.
- **Kiosk mode policy** — Always on / Always off / Auto (back on after a few minutes).
- **Screensaver style, away and guest mode** — Auto / No photos / Photos day and night / Screen off; black and off when nobody is home; clock only on the guest page.

## [1.1.0] — 2026-11-16

Inside temperature range.

- **"21–23° inside"** on the Home page: the lowest and highest of your rooms' temperature sensors from `my_home.yaml` (shown when two or more rooms have one). Re-run `python tools/render.py` to get it.

## [1.0.0] — 2026-11-09

Wall-tablet and phone dashboards from one file.

- **Tablet:** clock and weather, an attention strip that only shows what needs doing, one tap to every room, Security and Energy pages. Optional kiosk mode (with an admin toggle that brings the header back) and a photo screensaver.
- **Phone:** the same pages in one column with a floating bottom tab bar and ← back on every page. Never kiosk mode.
- Attention strip: open doors and windows, low batteries, lights left on with nobody home. Anything with your *ignore* label is skipped.
- **Panel blueprints:** Leaving button + countdown ("I'm staying" puts every light and speaker back), note by voice, rain soon, welcome home, admin mode that switches itself off.
- **Theme:** Wall Panel (frosted glass, dark).

[1.12.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.12.0
[1.11.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.11.0
[1.10.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.10.0
[1.9.2]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.9.2
[1.9.1]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.9.1
[1.9.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.9.0
[1.8.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.8.0
[1.7.1]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.7.1
[1.7.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.7.0
[1.6.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.6.0
[1.5.2]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.5.2
[1.5.1]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.5.1
[1.5.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.5.0
[1.4.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.4.0
[1.3.1]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.3.1
[1.3.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.3.0
[1.2.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.2.0
[1.1.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.1.0
[1.0.0]: https://github.com/davidteles/ha-wall-panel-kit/releases/tag/v1.0.0
