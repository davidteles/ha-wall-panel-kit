#!/usr/bin/env python3
"""Build a tablet and a phone dashboard from my_home.yaml.

    python tools/render.py                      # reads my_home.yaml
    python tools/render.py my_home.example.yaml # try it with the example
    python tools/render.py examples/one_room.yaml --out out-test

Writes out/tablet.yaml and out/phone.yaml (or into --out DIR). If they are
already there, the old ones are moved to out/previous/ first, so the last
version is always one copy away. Paste each into a new dashboard:
Settings → Dashboards → Add dashboard → open it → ⋮ → Edit → ⋮ → Raw configuration editor.

Both layouts share the same cards; only the frame differs:
- tablet: optional kiosk mode and photo screensaver, top tabs;
- phone: no kiosk ever, a floating bottom tab bar (navbar-card), every page but Home is a subview.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- helpers

def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def tile(entity: str, columns: int = 6, **extra) -> dict:
    return {"type": "tile", "entity": entity, "grid_options": {"columns": columns}, **extra}


def heading(text: str, icon: str | None = None) -> dict:
    card = {"type": "heading", "heading": text}
    if icon:
        card["icon"] = icon
    return card


def nav_card(name: str, icon: str, path: str, secondary: str = "", color: str = "blue") -> dict:
    return {
        "type": "custom:mushroom-template-card",
        "primary": name,
        "secondary": secondary,
        "icon": icon,
        "color": color,
        "tap_action": {"action": "navigate", "navigation_path": path},
        "grid_options": {"columns": 6},
    }


def jinja_list(entities: list[str]) -> str:
    return "[" + ", ".join(f"'{e}'" for e in entities) + "]"


# ---------------------------------------------------------------- shared cards

def alert_strip(home: dict) -> dict:
    """One markdown card listing what needs attention; hidden when there is nothing."""
    lights = [l for r in home["rooms"] for l in r.get("lights", [])]
    label = home.get("ignore_label", "")
    # A thermostat's guessed "open window" (tado, Netatmo valves) and a car's doors
    # and windows sit on a device that also has a climate entity: not the house.
    skip_climate = (
        "{%- set dev = device_id(s.entity_id) -%}"
        "{%- if not (dev and device_entities(dev) | select('match', 'climate\\\\.') | list | count > 0) -%}"
        if home.get("skip_climate_devices", True) else "{%- if true -%}"
    )
    template = (
        "{%- set ns = namespace(items=[]) -%}\n"
        f"{{%- set lbl = '{label}' -%}}"
        "{%- set ignore = (label_entities(lbl) + (label_devices(lbl) | map('device_entities') | sum(start=[]))) if lbl else [] -%}\n"
        "{%- for s in states.binary_sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'in', ['door', 'window', 'garage_door'])"
        " | selectattr('state', 'eq', 'on') | rejectattr('entity_id', 'in', ignore) -%}"
        + skip_climate
        + "{%- set ns.items = ns.items + ['🚪 ' ~ s.name ~ ' is open'] -%}{%- endif -%}{%- endfor -%}\n"
        "{%- for s in states.sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'eq', 'battery')"
        " | selectattr('state', 'is_number') | rejectattr('entity_id', 'in', ignore) -%}"
        "{%- if s.state | float(100) < 15 -%}"
        "{%- set ns.items = ns.items + ['🪫 ' ~ s.name ~ ' ' ~ s.state ~ '%'] -%}{%- endif -%}{%- endfor -%}\n"
        f"{{%- set on = expand({jinja_list(lights)}) | selectattr('state', 'eq', 'on') | list | count -%}}\n"
        "{%- if states('zone.home') | int(1) == 0 and on > 0 -%}"
        "{%- set ns.items = ns.items + ['💡 ' ~ on ~ (' light' if on == 1 else ' lights') ~ ' on and nobody home'] -%}{%- endif -%}\n"
        + rain_line(home)
        + entry_line(home)
        + laundry_line(home)
        + extra_lines(home)
        + match_line(home)
        + "{{ ns.items | join('<br>') }}"
    )
    return {
        "type": "markdown",
        "content": template,
        "show_empty": False,  # no empty box when there is nothing to say
        "grid_options": {"columns": 12},
        "card_mod": {"style": "ha-card { border-left: 4px solid var(--warning-color) !important; }"},
    }


def extra_lines(home: dict) -> str:
    """Your own lines for the attention strip: `extra_alerts: [{entity, text, state?}]`."""
    out = ""
    for a in home.get("extra_alerts") or []:
        state = str(a.get("state", "on"))
        text = str(a["text"]).replace("\\", "\\\\").replace("'", "\\'")
        out += (f"{{%- if is_state('{a['entity']}', '{state}') -%}}"
                f"{{%- set ns.items = ns.items + ['{text}'] -%}}{{%- endif -%}}\n")
    return out


def panel(home: dict) -> dict:
    return home.get("panel") or {}


def rain_line(home: dict) -> str:
    rain = panel(home).get("rain_at")
    if not rain:
        return ""
    return (
        f"{{%- set r = states('{rain}') -%}}"
        "{%- if r not in ['', 'unknown', 'unavailable'] -%}"
        "{%- set ns.items = ['☔ Rain ' ~ ('now' if r == 'now' else 'from ' ~ r) ~ ' — take an umbrella'] + ns.items -%}"
        "{%- endif -%}\n"
    )


# ---------------------------------------------------------------- entry (doorbell / intercom)

def entry(home: dict) -> dict:
    return home.get("entry") or {}


def entry_line(home: dict) -> str:
    e = entry(home)
    if not e.get("ringing"):
        return ""
    return (
        f"{{%- if is_state('{e['ringing']}', 'on') -%}}"
        f"{{%- set ns.items = ['🔔 Someone at the {e.get('name', 'door').lower()}'] + ns.items -%}}"
        "{%- endif -%}\n"
    )


def entry_camera(e: dict) -> dict:
    """Live video; with talk_stream, the WebRTC Camera card with the microphone for two-way talk."""
    if e.get("talk_stream"):
        return {"type": "custom:webrtc-camera", "url": e["talk_stream"], "media": "video,audio,microphone",
                **({"entity": e["camera"]} if e.get("camera") else {}), "grid_options": {"columns": 12}}
    return {"type": "picture-entity", "entity": e["camera"], "camera_view": "live", "show_state": False,
            "show_name": False, "grid_options": {"columns": 12}}


def door_button(door: dict, columns: int) -> dict:
    target = door["open"]
    domain = target.split(".")[0]
    action = {"script": "script.turn_on", "lock": "lock.open", "button": "button.press",
              "input_button": "input_button.press", "cover": "cover.open_cover"}.get(domain, "script.turn_on")
    return {
        "type": "custom:mushroom-template-card",
        "primary": door["name"],
        "secondary": "Tap to open",
        "icon": door.get("icon", "mdi:door-open"),
        "color": "green",
        "tap_action": {"action": "perform-action", "perform_action": action, "target": {"entity_id": target},
                       "confirmation": {"text": f"Open the {door['name'].lower()}?"}},
        "grid_options": {"columns": columns},
    }


def quick_replies(e: dict) -> list[dict]:
    """'Coming!' and the like, spoken through the doorbell's speaker — for doorbells without two-way talk."""
    if not (e.get("speaker") and e.get("tts") and e.get("replies")):
        return []
    chips = [{
        "type": "template",
        "icon": "mdi:message-reply-text",
        "content": text,
        "tap_action": {"action": "perform-action", "perform_action": "tts.speak", "target": {"entity_id": e["tts"]},
                       "data": {"media_player_entity_id": e["speaker"], "message": text}},
    } for text in e["replies"]]
    return [{"type": "custom:mushroom-chips-card", "alignment": "center", "chips": chips}]


def entry_sections(home: dict) -> list[dict]:
    e = entry(home)
    name = e.get("name", "Door")
    cards: list[dict] = [heading(name, "mdi:doorbell-video")]
    if e.get("ringing"):
        last = e.get("last_ring")
        cards.append({
            "type": "custom:mushroom-template-card",
            "icon": "mdi:bell-ring",
            "color": f"{{{{ 'red' if is_state('{e['ringing']}', 'on') else 'grey' }}}}",
            "primary": f"{{{{ 'Someone is at the {name.lower()}' if is_state('{e['ringing']}', 'on') else 'Nobody is ringing' }}}}",
            # The helper's timestamp attribute, not its state: the state has no time zone.
            "secondary": (f"{{% set ts = state_attr('{last}', 'timestamp') %}}{{{{ ('Last ring ' ~ ts | timestamp_custom('%a %H:%M')) if ts else 'No rings yet' }}}}"
                          if last else ""),
            "tap_action": {"action": "perform-action", "perform_action": "input_boolean.turn_off",
                           "target": {"entity_id": e["ringing"]}},
            "grid_options": {"columns": 12},
        })
    if e.get("camera") or e.get("talk_stream"):
        cards.append(entry_camera(e))
    cards += [{**c, "grid_options": {"columns": 12}} for c in quick_replies(e)]
    doors = e.get("doors") or []
    for door in doors:
        cards.append(door_button(door, 12 if len(doors) == 1 else 6))
    return [{"type": "grid", "cards": cards}]


OVERLAY_STYLE = """:host {
  position: fixed !important;
  inset: 0 !important;
  z-index: 8;
  display: flex !important;
  align-items: center;
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
  background: rgba(45, 0, 0, 0.62);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}
ha-card {
  width: min(520px, 100%) !important;
  max-height: calc(100vh - 32px);
  overflow-y: auto !important;
  box-sizing: border-box;
  padding: 14px 18px 18px !important;
  border-radius: 28px !important;
  background: rgba(26, 14, 16, 0.95) !important;
  border: 2px solid rgba(255, 59, 48, 0.85) !important;
  animation: wp-entry-pulse 1.2s ease-in-out infinite;
}
@keyframes wp-entry-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 59, 48, 0), 0 24px 70px rgba(0, 0, 0, 0.6); }
  50% { box-shadow: 0 0 40px 6px rgba(255, 59, 48, 0.55), 0 24px 70px rgba(0, 0, 0, 0.6); }
}
@media (orientation: landscape) and (min-width: 700px) and (max-height: 920px) {
  ha-card { width: min(980px, 100%) !important; }
}"""

# Landscape tablets: camera on the left, the text and the buttons on the right.
OVERLAY_LANDSCAPE = """@media (orientation: landscape) and (min-width: 700px) and (max-height: 920px) {
  #root { display: grid !important; grid-template-columns: 3fr 2fr; grid-template-rows: auto auto 1fr; column-gap: 24px; row-gap: 12px; align-items: center; }
  #root > *:nth-child(1) { grid-column: 2; grid-row: 1; }
  #root > *:nth-child(2) { grid-column: 1; grid-row: 1 / span 3; }
  #root > *:nth-child(3) { grid-column: 2; grid-row: 2; align-self: start; }
  #root > *:nth-child(4) { grid-column: 2; grid-row: 3; align-self: start; }
}"""

FLAT = """ha-card { background: transparent !important; border: none !important; box-shadow: none !important;
  -webkit-backdrop-filter: none !important; backdrop-filter: none !important; }"""


def opened_template(e: dict) -> str:
    """Sets `opened` to the name of a door whose script ran in the last 30 s ('' otherwise) and `verb` to
    what is known about it: 'opened' / 'unlocked' / 'opening' only when that door's optional `confirm`
    sensor CHANGED to that after the tap, otherwise 'sent' (the command went out, nothing confirms it)."""
    rows = [(d["name"], d["open"], d.get("confirm") or "") for d in e.get("doors") or []
            if str(d.get("open", "")).startswith("script.")]
    if not rows:
        return "{% set opened = '' %}{% set verb = '' %}"
    items = ", ".join(f"('{n}', '{x}', '{c}')" for n, x, c in rows)
    return ("{% set ns = namespace(o='', v='') %}"
            f"{{% for n, x, c in [{items}] %}}{{% set t = state_attr(x, 'last_triggered') %}}"
            "{% if t and (now() - t).total_seconds() < 30 %}{% set ns.o = n %}{% set ns.v = 'sent' %}"
            "{% set s = states[c] if c else none %}"
            "{% if s is not none and s.last_changed >= t %}"
            "{% if s.state in ['on', 'open'] %}{% set ns.v = 'opened' %}"
            "{% elif s.state == 'unlocked' %}{% set ns.v = 'unlocked' %}"
            "{% elif s.state == 'opening' %}{% set ns.v = 'opening' %}{% endif %}"
            "{% endif %}{% endif %}{% endfor %}"
            "{% set opened = ns.o %}{% set verb = ns.v %}")


def entry_overlay(home: dict) -> list[dict]:
    """The pop-up built into the dashboard (like an alarm takeover): needs only card-mod, no browser add-on.

    It covers whatever page is open while the ringing toggle is on, and goes away when a door is opened,
    Dismiss is pressed or the ring time runs out.
    """
    e = entry(home)
    if not e.get("ringing") or e.get("popup", "card") != "card":
        return []
    name = e.get("name", "door").lower()
    last = e.get("last_ring")
    header = {
        "type": "custom:mushroom-template-card",
        # Right after a door script runs, the header says what is known: opened / unlocked / opening only
        # when the door's `confirm` sensor changed after the tap, otherwise just "Open sent".
        "primary": (opened_template(e) + "{% if not opened %}Someone's at the door"
                    "{% elif verb == 'opened' %}✓ {{ opened }} opened{% elif verb == 'unlocked' %}🔓 {{ opened }} unlocked"
                    "{% elif verb == 'opening' %}{{ opened }} opening…{% else %}Open sent to {{ opened }}{% endif %}"),
        "secondary": (f"{{% set ts = state_attr('{last}', 'timestamp') %}}{e.get('name', 'Door')}{{{{ (' · rang at ' ~ ts | timestamp_custom('%H:%M')) if ts else '' }}}}"
                      if last else e.get("name", "Door")),
        "icon": opened_template(e) + "{{ {'opened': 'mdi:door-open', 'opening': 'mdi:door-open', 'unlocked': 'mdi:lock-open-variant',"
                                     " 'sent': 'mdi:send'}.get(verb, 'mdi:bell-ring') }}",
        "icon_color": opened_template(e) + "{{ {'opened': 'green', 'opening': 'green', 'unlocked': 'green', 'sent': 'amber'}.get(verb, 'red') }}",
        "layout": "vertical",
        "tap_action": {"action": "none"},
        "hold_action": {"action": "none"},
        "card_mod": {"style": FLAT + """
ha-card { --ha-tile-info-primary-font-size: 26px; --ha-tile-info-primary-line-height: 32px;
  --ha-tile-info-secondary-font-size: 15px; --card-primary-font-size: 26px; --card-secondary-font-size: 15px; }
ha-tile-icon, mushroom-shape-icon { --tile-icon-size: 64px; --icon-size: 64px; --mdc-icon-size: 38px;
  animation: wp-entry-icon 1s ease-in-out infinite; }
@keyframes wp-entry-icon { 0%, 100% { transform: rotate(0); } 25% { transform: rotate(-12deg); } 75% { transform: rotate(12deg); } }"""},
    }
    camera = entry_camera(e) if (e.get("camera") or e.get("talk_stream")) else {"type": "markdown", "content": " "}
    camera = {k: v for k, v in camera.items() if k != "grid_options"}
    camera["card_mod"] = {"style": "ha-card { border-radius: 18px !important; overflow: hidden; }"}
    buttons = []
    for door in e.get("doors") or []:
        b = door_button(door, 6)
        b.pop("grid_options", None)
        b["layout"] = "vertical"
        b["card_mod"] = {"style": "ha-card { background: rgba(48, 209, 88, 0.16) !important;"
                                  " border: 1px solid rgba(48, 209, 88, 0.55) !important; --card-primary-font-size: 18px; }"}
        buttons.append(b)
    buttons.append({
        "type": "custom:mushroom-template-card", "primary": "Dismiss", "icon": "mdi:close", "color": "grey",
        "layout": "vertical",
        "tap_action": {"action": "perform-action", "perform_action": "input_boolean.turn_off",
                       "target": {"entity_id": e["ringing"]}},
    })
    return [{
        "type": "custom:mod-card",
        "visibility": [{"condition": "state", "entity": e["ringing"], "state": "on"}],
        "grid_options": {"columns": 12},
        "card_mod": {"style": {"hui-vertical-stack-card$": OVERLAY_LANDSCAPE, ".": OVERLAY_STYLE}},
        "card": {"type": "vertical-stack", "cards": [header, camera] + quick_replies(e) + [
            # As many columns as buttons (up to 3): one door → two wide buttons, two doors → three.
            {"type": "grid", "columns": min(len(buttons), 3), "square": False, "cards": buttons},
        ]},
    }]


# Landscape tablets: the message and countdown on the left, the PIN pad on the right.
ALARM_LANDSCAPE = """@media (orientation: landscape) and (min-width: 700px) and (max-height: 920px) {
  #root { display: grid !important; grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr; column-gap: 24px; align-items: center; }
  #root > *:nth-child(1) { grid-column: 1; grid-row: 1; }
  #root > *:nth-child(2) { grid-column: 1; grid-row: 2; align-self: start; }
  #root > *:nth-child(3) { grid-column: 2; grid-row: 1 / span 2; }
}"""


def alarm_overlay(home: dict) -> list[dict]:
    """Alarm takeover: while the alarm counts down to going off (pending) or is going off (triggered),
    a red pop-up covers every page with what was opened, the countdown and the PIN pad."""
    cfg = home.get("alarm_takeover")
    alarm = home.get("alarm")
    if not cfg or not alarm:
        return []
    cfg = cfg if isinstance(cfg, dict) else {}
    what = (f"{{% set os = state_attr('{alarm}', 'open_sensors') or {{}} %}}"
            "{% set n = os.keys() | map('state_attr', 'friendly_name') | reject('none') | list %}"
            "{% set what = n | join(', ') if n else 'a door or sensor' %}")
    header = {
        "type": "custom:mushroom-template-card",
        "primary": f"{{{{ 'Enter your PIN' if is_state('{alarm}', 'pending') else 'The alarm is going off' }}}}",
        "secondary": what + f"{{% if is_state('{alarm}', 'pending') %}}{{{{ what[:1] | upper ~ what[1:] }}}} opened while the alarm was on."
                     " Turn it off before the countdown ends.{% else %}"
                     f"Set off by {{{{ what }}}} at {{{{ as_local(states['{alarm}'].last_changed).strftime('%H:%M') }}}}."
                     " Enter your PIN to turn it off.{% endif %}",
        "icon": f"{{{{ 'mdi:shield-alert' if is_state('{alarm}', 'pending') else 'mdi:alarm-light' }}}}",
        "icon_color": "red",
        "layout": "vertical",
        "multiline_secondary": True,
        "tap_action": {"action": "none"},
        "hold_action": {"action": "none"},
        "card_mod": {"style": FLAT + """
ha-card { --card-primary-font-size: 26px; --card-secondary-font-size: 15px;
  --ha-tile-info-primary-font-size: 26px; --ha-tile-info-secondary-font-size: 15px; }
ha-tile-icon, mushroom-shape-icon { --tile-icon-size: 64px; --icon-size: 64px; --mdc-icon-size: 38px;
  animation: wp-alarm-icon 1s ease-in-out infinite; }
@keyframes wp-alarm-icon { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.12); } }"""},
    }
    countdown: dict = {"type": "markdown", "content": " ", "card_mod": {"style": FLAT}}
    if cfg.get("countdown"):
        countdown = {
            "type": "conditional",
            "conditions": [{"condition": "state", "entity": cfg["countdown"], "state": "active"}],
            "card": {"type": "tile", "entity": cfg["countdown"], "name": "The alarm goes off in", "vertical": True,
                     "tap_action": {"action": "none"}, "icon_tap_action": {"action": "none"},
                     "card_mod": {"style": """ha-card { background: rgba(255, 59, 48, 0.12) !important;
  border: 1px solid rgba(255, 59, 48, 0.45) !important; --ha-tile-info-primary-font-size: 15px;
  --ha-tile-info-secondary-font-size: 56px; --ha-tile-info-secondary-font-weight: 700;
  --ha-tile-info-secondary-line-height: 62px; --ha-tile-info-secondary-color: #ff453a; }
ha-tile-icon { display: none !important; }"""}},
        }
    pad = {
        "type": "alarm-panel", "entity": alarm, "name": cfg.get("name", "Alarm"), "states": [],
        "card_mod": {"style": FLAT + """
.card-header { display: none; }
#armActions ha-button::part(base) { height: 64px; font-size: 1.4em; font-weight: 700; border-radius: 32px; background: #ff3b30; color: #fff; }"""},
    }
    return [{
        "type": "custom:mod-card",
        "visibility": [{"condition": "state", "entity": alarm, "state": ["pending", "triggered"]}],
        "grid_options": {"columns": 12},
        "card_mod": {"style": {"hui-vertical-stack-card$": ALARM_LANDSCAPE, ".": OVERLAY_STYLE}},
        "card": {"type": "vertical-stack", "cards": [header, countdown, pad]},
    }]


def with_overlay(home: dict, sections: list[dict]) -> list[dict]:
    """Put the pop-ups (alarm takeover, entry) in the first section of a page, so they show on every page."""
    overlay = alarm_overlay(home) + entry_overlay(home)
    if not overlay or not sections:
        return sections
    return [{**sections[0], "cards": overlay + sections[0]["cards"]}] + sections[1:]


def entry_home_card(home: dict) -> list[dict]:
    """A red card on Home while someone is ringing (when the pop-up is not the built-in one); tap goes to the Entry page."""
    e = entry(home)
    if not e.get("ringing") or e.get("popup", "card") == "card":
        return []
    return [{
        "type": "custom:mushroom-template-card",
        "icon": "mdi:bell-ring",
        "color": "red",
        "primary": f"Someone at the {e.get('name', 'door').lower()}",
        "secondary": "Tap to see and answer",
        "tap_action": {"action": "navigate", "navigation_path": f"{home['_base']}/entry"},
        "visibility": [{"condition": "state", "entity": e["ringing"], "state": "on"}],
        "grid_options": {"columns": 12},
        "card_mod": {"style": "ha-card { background: rgba(244, 67, 54, 0.22) !important;"
                              " border: 1px solid rgba(244, 67, 54, 0.6) !important; }"},
    }]


# ---------------------------------------------------------------- match (Team Tracker)

def match(home: dict) -> dict:
    return home.get("match") or {}


def match_entity_expr(m: dict) -> str:
    """Jinja expression for the Team Tracker sensor to show: `match.source` (a template sensor whose state is
    that sensor's entity id, for several competitions) or the fixed `match.sensor`."""
    if m.get("source"):
        return f"states('{m['source']}')"
    return f"'{m['sensor']}'"


# Team Tracker's `clock` is ESPN's short status: "67'", "HT" at half time (still state IN), "FT" after.
_HT = "['ht', 'halftime', 'half time', 'half-time']"


def match_card(home: dict) -> list[dict]:
    """A slim strip on Home while `match.window` is on: both logos, the kick-off time or the score with the
    minute under it, and the status (Live / Half time / Full time, or GOAL! for a few minutes) with the competition."""
    m = match(home)
    if not (m.get("sensor") or m.get("source")):
        return []
    watched = m.get("source") or m["sensor"]
    goal = ""
    if m.get("goal_alert") and m.get("goal_by"):
        goal = (f"{{%- set goal = is_state('{m['goal_alert']}', 'on') -%}}"
                f"{{%- set gby = states('{m['goal_by']}') -%}}\n")
    else:
        goal = "{%- set goal = false -%}{%- set gby = '' -%}\n"
    content = (
        f"{{%- set e = {match_entity_expr(m)} -%}}\n"
        "{%- set s = states(e) -%}\n"
        "{%- set home = state_attr(e, 'team_homeaway') != 'away' -%}\n"
        "{%- set t = 'team' if home else 'opponent' -%}{%- set o = 'opponent' if home else 'team' -%}\n"
        "{%- set c = state_attr(e, 'clock') | string -%}\n"
        f"{{%- set ht = s == 'IN' and c | lower in {_HT} -%}}\n"
        "{%- set k = state_attr(e, 'date') | as_datetime(none) -%}\n"
        "{%- set g1 = state_attr(e, t ~ '_score') -%}{%- set g2 = state_attr(e, o ~ '_score') -%}\n"
        + goal +
        "<table><tr>\n"
        "<td><img src=\"{{ state_attr(e, t ~ '_logo') }}\"></td>\n"
        "<td><h2>{% if s == 'PRE' %}{{ (k | as_local).strftime('%H:%M') if k else '–' }}"
        "{% else %}{{ g1 if g1 is not none else 0 }}<font color=\"#8a8f98\">-</font>{{ g2 if g2 is not none else 0 }}{% endif %}</h2>"
        "<b><font color=\"#4ade80\">{% if s == 'PRE' %}Kick-off{% elif ht %}HT{% elif s == 'POST' %}FT{% else %}{{ c }}{% endif %}</font></b></td>\n"
        "<td><img src=\"{{ state_attr(e, o ~ '_logo') }}\"></td>\n"
        "<td><b>{% if s == 'IN' and goal and gby == state_attr(e, 'team_name') %}<font color=\"#4ade80\">⚽ GOAL!</font>"
        "{% elif s == 'IN' and goal %}<font color=\"#ff5a5a\">Goal {{ gby }}</font>"
        "{% elif ht %}<font color=\"#f5b942\">● Half time</font>{% elif s == 'IN' %}<font color=\"#ff5a5a\">● Live</font>"
        "{% elif s == 'POST' %}Full time{% else %}{{ 'Today' if k and (k | as_local).date() == now().date() else '' }}{% endif %}</b>"
        "<br>{{ state_attr(e, 'league_name') or '' }}</td>\n"
        "</tr></table>\n"
    )
    inner = (
        "table, tr, th, td { border: none !important; background: none !important; }\n"
        "table { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0; }\n"
        "td { vertical-align: middle; text-align: center; padding: 0; }\n"
        "td:nth-child(1), td:nth-child(3) { width: 40px; }\n"
        "td:nth-child(2) { width: 74px; }\n"
        "td:nth-child(2) b { display: block; font-size: 0.72rem; line-height: 1.1; margin-top: 2px; }\n"
        "td:nth-child(4) { text-align: right; padding-left: 8px; font-size: 0.72rem; line-height: 1.25; opacity: 0.85;"
        " white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
        "td:nth-child(4) b { font-size: 0.92rem; }\n"
        "img { width: 32px; height: 32px; object-fit: contain; display: block; margin: 0 auto; }\n"
        "h2 { margin: 0; font-size: 1.35rem; line-height: 1; font-weight: 800; white-space: nowrap; }\n"
    )
    return [{
        "type": "markdown",
        # Home Assistant follows the entities the template reads by itself; entity_id just names the card's subject.
        "entity_id": [watched],
        "content": content,
        "grid_options": {"columns": 12},
        "visibility": [{"condition": "state", "entity": m["window"], "state": "on"}],
        "card_mod": {"style": {
            ".": "ha-card { padding: 0 14px !important; height: 56px; box-sizing: border-box;"
                 " display: flex; flex-direction: column; justify-content: center; }\n"
                 "ha-markdown { padding: 0 !important; }\n",
            "ha-markdown $": inner,
        }},
    }]


def match_line(home: dict) -> str:
    """'⚽ GOAL <team>! 2–1' as the first line of the attention strip while `match.goal_alert` is on."""
    m = match(home)
    if not ((m.get("sensor") or m.get("source")) and m.get("goal_alert") and m.get("goal_by")):
        return ""
    return (
        f"{{%- if is_state('{m['goal_alert']}', 'on') -%}}"
        f"{{%- set me = {match_entity_expr(m)} -%}}"
        f"{{%- set by = states('{m['goal_by']}') -%}}"
        "{%- set ns.items = ['⚽ <b>GOAL ' ~ by ~ ('!' if by == state_attr(me, 'team_name') else '') ~ '</b> '"
        " ~ (state_attr(me, 'team_score') or 0) ~ '–' ~ (state_attr(me, 'opponent_score') or 0)"
        " ~ ' ' ~ (state_attr(me, 'clock') or '')] + ns.items -%}"
        "{%- endif -%}\n"
    )


# ---------------------------------------------------------------- laundry

def laundry(home: dict) -> dict:
    return home.get("laundry") or {}


def laundry_line(home: dict) -> str:
    l = laundry(home)
    if not l.get("waiting"):
        return ""
    out = (f"{{%- if is_state('{l['waiting']}', 'on') -%}}"
           "{%- set ns.items = ns.items + ['🧺 Laundry ready to hang'] -%}{%- endif -%}\n")
    if l.get("rain_alert"):
        out += (f"{{%- if is_state('{l['rain_alert']}', 'on') -%}}"
                "{%- set ns.items = ['☔ Laundry is outside and rain is coming'] + ns.items -%}{%- endif -%}\n")
    return out


def _state(entity: str, state) -> dict:
    return {"condition": "state", "entity": entity, "state": state}


def _laundry_button(name: str, icon: str, place: str, script: str, visibility: list, color: str = "blue",
                    secondary: str = "", columns: int = 4, confirm: str | None = None, step: str = "hung") -> dict:
    """A button with no `entity`: tapping its icon can never toggle a helper by accident.

    `step` tells the Laundry hung script what the tap means: "hung" (the answer, only while waiting) or
    "move" (where it's drying, only once on the rack), so a late tap can't overwrite an answer."""
    action = {"action": "perform-action", "perform_action": script, "data": {"place": place, "step": step}}
    if confirm:
        action["confirmation"] = {"text": confirm}
    card = {"type": "custom:mushroom-template-card", "primary": name, "icon": icon, "color": color,
            "layout": "vertical", "tap_action": action, "icon_tap_action": action,
            "visibility": visibility, "grid_options": {"columns": columns}}
    if secondary:
        card["secondary"] = secondary
    return card


def laundry_cards(home: dict) -> list[dict]:
    """Laundry on Home: the advice and Hung indoors / outside / nothing while it waits; where it dries afterwards."""
    l = laundry(home)
    if not l.get("waiting"):
        return []
    waiting = [_state(l["waiting"], "on")]
    adv = (f"{{% set a = (states('{l['advice']}') ~ '||||').split('|') %}}" if l.get("advice") else "{% set a = ['', ''] %}")
    finished = (f"{{% set ts = state_attr('{l['finished_at']}', 'timestamp') %}}{{{{ (' · finished ' ~ ts | timestamp_custom('%H:%M')) if ts else '' }}}}"
                if l.get("finished_at") else "")
    cards: list[dict] = [{
        "type": "custom:mushroom-template-card",
        "icon": "mdi:washing-machine-alert",
        "color": "blue",
        "primary": adv + "Laundry ready to hang{{ {'outdoors': ' · outside recommended', 'indoors': ' · indoors recommended'}.get(a[0], '') }}",
        "secondary": adv + "{{ a[1] if a[1] else 'Choose where you hung it' }}" + finished,
        "multiline_secondary": True,
        "tap_action": {"action": "none"}, "icon_tap_action": {"action": "none"},
        "visibility": waiting, "grid_options": {"columns": 12},
    }]
    if not (l.get("place") and l.get("script")):
        # Without the dropdown: one "it's out" button that clears the waiting toggle.
        off = {"action": "perform-action", "perform_action": "input_boolean.turn_off", "target": {"entity_id": l["waiting"]}}
        cards[0].update({"secondary": "Tap when it's out of the machine" + finished, "tap_action": off, "icon_tap_action": off})
        return cards
    script, place = l["script"], l["place"]

    def choice(name: str, icon: str, place_name: str, advice: str) -> dict:
        """Indoors / Outside: the same size; the recommended one gets a 'Recommended' label and a subtle
        accent border (card-mod). Advice only: nothing is preselected, a tap is the only confirmation."""
        b = _laundry_button(name, icon, place_name, script, waiting, columns=6,
                            secondary=adv + f"{{{{ 'Recommended' if a[0] == '{advice}' else '\u200b' }}}}")  # same height either way: a zero-width space survives template trimming
        b["card_mod"] = {"style": adv + "ha-card { {% if a[0] == '" + advice + "' %}border: 1.5px solid rgba(76, 175, 80, 0.65) !important;{% endif %} }"}
        return b

    nothing = {"action": "perform-action", "perform_action": script, "data": {"place": "Not hung", "step": "hung"},
               "confirmation": {"text": "Nothing to hang from this cycle?"}}
    cards += [
        choice("Hung indoors", "mdi:home", "Indoors", "indoors"),
        choice("Hung outside", "mdi:weather-sunny", "Outside", "outdoors"),
        # A secondary action, smaller than the two choices (chips have no entity, so no icon toggle).
        {"type": "custom:mushroom-chips-card", "alignment": "center", "visibility": waiting,
         "grid_options": {"columns": 12},
         "chips": [{"type": "template", "icon": "mdi:close-circle-outline", "content": "Nothing to hang",
                    "tap_action": nothing, "hold_action": {"action": "none"}}]},
    ]
    if l.get("on_rack"):
        not_set = [_state(l["on_rack"], "on"), _state(place, l.get("not_set_option", "Not set"))]
        cards += [{
            "type": "custom:mushroom-template-card", "icon": "mdi:hanger", "color": "orange",
            "primary": "Laundry on the rack — where is it drying?",
            "secondary": "Indoors or outside, so the right things happen",
            "tap_action": {"action": "none"}, "icon_tap_action": {"action": "none"},
            "visibility": not_set, "grid_options": {"columns": 12},
        },
            _laundry_button("Indoors", "mdi:home", "Indoors", script, not_set, columns=6, step="move"),
            _laundry_button("Outside", "mdi:weather-sunny", "Outside", script, not_set, columns=6, step="move")]
        change = {"action": "perform-action", "perform_action": script, "data": {"place": "Change", "step": "move"},
                  "confirmation": {"text": "Change where the laundry is drying?"}}
        drying = [_state(l["on_rack"], "on"), _state(place, ["Indoors", "Outside"])]
        if l.get("rain_alert"):
            drying.append(_state(l["rain_alert"], "off"))
        cards.append({
            "type": "custom:mushroom-template-card", "color": "grey",
            "icon": f"{{{{ 'mdi:home' if is_state('{place}', 'Indoors') else 'mdi:weather-sunny' }}}}",
            "primary": f"Drying {{{{ 'indoors' if is_state('{place}', 'Indoors') else 'outside' }}}}",
            "secondary": f"Tap to change to {{{{ 'outside' if is_state('{place}', 'Indoors') else 'indoors' }}}}",
            "tap_action": change, "icon_tap_action": change,
            "visibility": drying, "grid_options": {"columns": 12},
        })
    if l.get("rain_alert"):
        inside = {"action": "perform-action", "perform_action": script, "data": {"place": "Indoors", "step": "move"}}
        cards.append({
            "type": "custom:mushroom-template-card", "icon": "mdi:weather-pouring", "color": "red",
            "primary": "Laundry is outside — rain is coming",
            "secondary": "Tap when it's indoors",
            "tap_action": inside, "icon_tap_action": inside,
            "visibility": [_state(l["rain_alert"], "on")], "grid_options": {"columns": 12},
        })
    return cards


def panel_cards(home: dict) -> list[dict]:
    """Welcome greeting, note and Leaving button + countdown (from the kit's blueprints)."""
    p = panel(home)
    cards: list[dict] = []
    if p.get("last_arrival"):
        cards.append({
            "type": "markdown",
            "show_empty": False,
            "content": (
                f"{{% set a = states('{p['last_arrival']}').split('|') %}}"
                "{% if a | count == 2 and (now().timestamp() - a[1] | float(0)) < 600 %}"
                "## Welcome home, {{ a[0] }} 👋{% endif %}"
            ),
            "grid_options": {"columns": 12},
        })
    if p.get("note"):
        frm = p.get("note_from")
        cards.append({
            "type": "custom:mushroom-template-card",
            "icon": "mdi:note-text",
            "color": "amber",
            "primary": f"{{{{ states('{p['note']}') }}}}",
            "secondary": (f"{{{{ ('from ' ~ states('{frm}') ~ ' · ') if states('{frm}') not in ['', 'unknown', 'unavailable'] else '' }}}}tap to clear" if frm else "Tap to clear"),
            "multiline_secondary": True,
            "tap_action": {
                "action": "perform-action",
                "perform_action": "input_text.set_value",
                "target": {"entity_id": p["note"]},
                "data": {"value": ""},
            },
            "visibility": [{"condition": "state", "entity": p["note"], "state_not": ["", "unknown", "unavailable"]}],
            "grid_options": {"columns": 12},
        })
    if p.get("leaving_script") and p.get("leaving_timer"):
        timer = p["leaving_timer"]
        idle = [{"condition": "state", "entity": timer, "state_not": "active"}]
        active = [{"condition": "state", "entity": timer, "state": "active"}]
        cards.append({
            "type": "custom:mushroom-template-card",
            "icon": "mdi:exit-run",
            "color": "blue",
            "primary": "Leaving",
            "secondary": "Lights off, music paused, alarm on in a minute",
            "tap_action": {"action": "perform-action", "perform_action": p["leaving_script"]},
            "visibility": idle,
            "grid_options": {"columns": 12},
        })
        cards.append({"type": "tile", "entity": timer, "name": "Leaving…", "icon": "mdi:exit-run",
                      "visibility": active, "grid_options": {"columns": 12}})
        for label, icon, service, color in (("I'm staying", "mdi:close", "timer.cancel", "grey"),
                                            ("Arm now", "mdi:shield-lock", "timer.finish", "red")):
            cards.append({
                "type": "custom:mushroom-template-card", "primary": label, "icon": icon, "color": color,
                "tap_action": {"action": "perform-action", "perform_action": service, "target": {"entity_id": timer}},
                "visibility": active, "grid_options": {"columns": 6},
            })
    return cards


def lights_summary(home: dict) -> dict:
    lights = [l for r in home["rooms"] for l in r.get("lights", [])]
    count = f"expand({jinja_list(lights)}) | selectattr('state', 'eq', 'on') | list | count"
    return {
        "type": "custom:mushroom-template-card",
        "icon": "mdi:lightbulb-group",
        "color": f"{{{{ 'amber' if {count} else 'grey' }}}}",
        "primary": f"{{% set n = {count} %}}{{{{ n }}}} {{{{ 'light' if n == 1 else 'lights' }}}} on",
        "secondary": "Tap to turn all off",
        "tap_action": {
            "action": "perform-action",
            "perform_action": "light.turn_off",
            "target": {"entity_id": lights},
            "confirmation": {"text": "Turn off all lights?"},
        },
        "grid_options": {"columns": 6},
    }


def inside_range(home: dict) -> list[dict]:
    """'21–23° inside' from the rooms' temperature sensors (lowest–highest), when there are two or more."""
    sensors = [r["temperature"] for r in home["rooms"] if r.get("temperature")]
    if len(sensors) < 2:
        return []
    values = (
        f"{{%- set t = {jinja_list(sensors)} | map('states') | select('is_number') | map('float') | list -%}}"
    )
    return [{
        "type": "custom:mushroom-template-card",
        "icon": "mdi:home-thermometer",
        "color": "orange",
        "primary": (
            values
            + "{%- if t | count == 0 -%}—{%- elif (t | min | round(0)) == (t | max | round(0)) -%}"
            "{{ t | min | round(0) | int }}° inside"
            "{%- else -%}{{ t | min | round(0) | int }}–{{ t | max | round(0) | int }}° inside{%- endif -%}"
        ),
        "secondary": f"Lowest and highest of {len(sensors)} rooms",
        "grid_options": {"columns": 6},
    }]


def home_sections(home: dict, phone: bool) -> list[dict]:
    # Clock Weather Card v3 options (v3 removed forecast_rows / time_format / hide_clock).
    weather = {
        "type": "custom:clock-weather-card",
        "entity": home["weather"],
        "sections": {
            "forecast_strip": {"hide": True},
            "forecast_list": {"count": 3 if phone else 5},
        },
    }
    if phone:  # the phone shows the time already: temperature, state and date only
        weather["sections"]["header"] = {"rows": [
            {"segments": [{"type": "icon", "icon": "mdi:thermometer"}, {"type": "weather", "attribute": "temperature"},
                          {"type": "spacer"}, {"type": "weather"}]},
            {"alignment": "center", "segments": [{"type": "icon", "icon": "mdi:calendar"}, {"type": "date"}]},
        ]}
    first = (entry_home_card(home) + [weather] + match_card(home) + inside_range(home) + panel_cards(home) + [alert_strip(home)]
             + laundry_cards(home) + [lights_summary(home)])
    if home.get("alarm"):
        first.append(tile(home["alarm"], 6, name="Alarm"))
    sections = [{"type": "grid", "cards": first}]

    people = home.get("people") or []
    if people:
        sections.append({"type": "grid", "cards": [heading("People", "mdi:account-group")]
                         + [tile(p, 6, vertical=True) for p in people]})

    rooms = [heading("Rooms", "mdi:floor-plan")]
    for room in home["rooms"]:
        secondary = ""
        if room.get("temperature"):
            secondary = f"{{{{ states('{room['temperature']}') }}}} °C"
        rooms.append(nav_card(room["name"], room.get("icon", "mdi:door"),
                              f"{home['_base']}/{slug(room['name'])}", secondary))
    sections.append({"type": "grid", "cards": rooms})

    if home.get("calendar"):
        sections.append({"type": "grid", "cards": [
            heading("Coming up", "mdi:calendar"),
            {"type": "calendar", "entities": [home["calendar"]], "initial_view": "listWeek"},
        ]})
    return sections


def room_sections(room: dict) -> list[dict]:
    cards = [heading(room["name"], room.get("icon"))]
    for key in ("temperature", "humidity"):
        if room.get(key):
            cards.append(tile(room[key], 6))
    for light in room.get("lights", []):
        cards.append(tile(light, 6, features=[{"type": "light-brightness"}]))
    if room.get("climate"):
        cards.append(tile(room["climate"], 12, features=[{"type": "target-temperature"}]))
    for cover in room.get("covers", []):
        cards.append(tile(cover, 6, features=[{"type": "cover-open-close"}]))
    if room.get("media"):
        cards.append({"type": "media-control", "entity": room["media"], "grid_options": {"columns": 12}})
    for other in room.get("other", []):
        cards.append(tile(other, 6))
    return [{"type": "grid", "cards": cards}]


def security_sections(home: dict) -> list[dict]:
    return [{"type": "grid", "cards": [
        heading("Security", "mdi:shield-home"),
        tile(home["alarm"], 12, features=[{"type": "alarm-modes",
                                           "modes": ["armed_home", "armed_away", "armed_night", "disarmed"]}]),
    ]}]


def energy_sections(home: dict) -> list[dict]:
    e = home["energy"]
    cards = [heading("Energy", "mdi:lightning-bolt")]
    if e.get("power_now"):
        cards.append({"type": "gauge", "entity": e["power_now"], "min": 0, "max": 6000,
                      "needle": True, "grid_options": {"columns": 12}})
    if e.get("energy_today"):
        cards.append(tile(e["energy_today"], 12, name="Today"))
    cards.append({"type": "energy-distribution", "link_dashboard": True, "grid_options": {"columns": 12}})
    return [{"type": "grid", "cards": cards}]


# ---------------------------------------------------------------- frames

def pages(home: dict) -> list[dict]:
    """(path, title, icon, sections) for every page, Home first."""
    out = [("home", "Home", "mdi:home", None)]
    out.append(("rooms", "Rooms", "mdi:floor-plan", [{"type": "grid", "cards": [
        nav_card(r["name"], r.get("icon", "mdi:door"), f"{home['_base']}/{slug(r['name'])}")
        for r in home["rooms"]]}]))
    if home.get("alarm"):
        out.append(("security", "Security", "mdi:shield-home", security_sections(home)))
    if home.get("energy"):
        out.append(("energy", "Energy", "mdi:lightning-bolt", energy_sections(home)))
    if home.get("entry"):
        out.append(("entry", "Entry", "mdi:doorbell-video", entry_sections(home)))  # short: it's a tab label
    return out


def navbar(home: dict) -> dict:
    routes = [{"url": f"{home['_base']}/{p}", "icon": i, "label": t} for p, t, i, _ in pages(home)]
    return {
        "type": "custom:navbar-card",
        "desktop": {"show_labels": True, "position": "bottom"},
        "mobile": {"show_labels": True, "mode": "floating"},
        "routes": routes,
    }


def tablet(home: dict) -> dict:
    home = {**home, "_base": "/wall-panel"}
    views = []
    for path, title, icon, sections in pages(home):
        views.append({"title": title, "path": path, "icon": icon, "type": "sections", "max_columns": 4,
                      "sections": with_overlay(home, sections or home_sections(home, phone=False))})
    for room in home["rooms"]:
        views.append({"title": room["name"], "path": slug(room["name"]), "icon": room.get("icon"),
                      "type": "sections", "subview": True, "back_path": "/wall-panel/rooms",
                      "sections": with_overlay(home, room_sections(room))})
    dash: dict = {"views": views}

    t = home.get("tablet") or {}
    if t.get("kiosk"):
        # Hide header and sidebar on touch tablets only — never on phones or computers.
        cond = "navigator.maxTouchPoints > 1 && !/iPhone|iPod|Android.+Mobile/.test(user_agent)"
        if t.get("admin_toggle"):
            cond += f" && !is_state('{t['admin_toggle']}', 'on')"
        dash["kiosk_mode"] = {"hide_header": f"[[[ {cond} ]]]", "hide_sidebar": f"[[[ {cond} ]]]"}
    if t.get("screensaver"):
        s = t["screensaver"]
        dash["wallpanel"] = {
            "enabled": True,
            "idle_time": int(s.get("idle_seconds", 180)),
            "display_time": 20,
            "image_url": s.get("photos", ""),
            "image_animation_ken_burns": True,
            "cards": [{"type": "clock", "clock_size": "large", "time_format": "24", "no_background": True}],
        }
    return dash


def phone(home: dict) -> dict:
    home = {**home, "_base": "/phone-home"}
    bar = navbar(home)
    views = []
    for path, title, icon, sections in pages(home):
        sections = with_overlay(home, sections or home_sections(home, phone=True))
        sections = [{**sections[0], "cards": [bar] + sections[0]["cards"]}] + sections[1:]
        view = {"title": title, "path": path, "icon": icon, "type": "sections", "max_columns": 1,
                "sections": sections}
        if path != "home":
            view.update({"subview": True, "back_path": "/phone-home/home"})
        views.append(view)
    for room in home["rooms"]:
        sections = with_overlay(home, room_sections(room))
        sections = [{**sections[0], "cards": [bar] + sections[0]["cards"]}]
        views.append({"title": room["name"], "path": slug(room["name"]), "icon": room.get("icon"),
                      "type": "sections", "max_columns": 1, "subview": True,
                      "back_path": "/phone-home/rooms", "sections": sections})
    return {"views": views}  # no kiosk_mode, no screensaver: phones keep their header.


# ---------------------------------------------------------------- main

ENTITY = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
SINGLE = ("weather", "calendar", "alarm")
ROOM_SINGLE = ("temperature", "humidity", "climate", "media")
ROOM_LISTS = ("lights", "covers", "other")
RESERVED = {"home", "rooms", "security", "energy", "entry"}
ENTRY_SINGLE = ("ringing", "last_ring", "camera", "speaker", "tts")
POPUPS = ("card", "browser_mod", "none")
LAUNDRY_KEYS = ("waiting", "finished_at", "advice", "place", "script", "on_rack", "rain_alert")
OPENERS = ("script", "lock", "button", "input_button", "cover")


def check(home) -> list[str]:
    """Every problem in the config, each naming the key it is about."""
    if not isinstance(home, dict):
        return ["the file must be a YAML mapping (title:, weather:, rooms: …)"]
    errors = [f"'{k}' is missing" for k in ("title", "weather", "rooms") if not home.get(k)]

    def entity(where: str, value) -> None:
        if not isinstance(value, str) or not ENTITY.match(value):
            errors.append(f"{where}: {value!r} is not an entity id (like light.kitchen)")

    for key in SINGLE:
        if home.get(key):
            entity(key, home[key])
    for i, person in enumerate(home.get("people") or []):
        entity(f"people[{i}]", person)
    mt = home.get("match")
    if mt is not None:
        if not isinstance(mt, dict):
            errors.append("match: must be a mapping (sensor:, window:, goal_alert:, goal_by:)")
        else:
            if not (mt.get("sensor") or mt.get("source")):
                errors.append("match: 'sensor' is missing (your Team Tracker sensor, e.g. sensor.my_team, "
                              "or 'source' for several competitions)")
            for key in ("sensor", "source"):
                if mt.get(key) and not str(mt[key]).startswith("sensor."):
                    errors.append(f"match {key}: {mt[key]!r} must be a sensor (docs/match.md)")
            if not mt.get("window"):
                errors.append("match: 'window' is missing (the binary_sensor that is on around the match, docs/match.md)")
            elif not str(mt["window"]).startswith("binary_sensor."):
                errors.append(f"match window: {mt['window']!r} must be a binary_sensor (docs/match.md)")
            if bool(mt.get("goal_alert")) != bool(mt.get("goal_by")):
                errors.append("match: set 'goal_alert' and 'goal_by' together (or neither)")
            for key, dom in (("goal_alert", "binary_sensor."), ("goal_by", "input_text.")):
                if mt.get(key) and not str(mt[key]).startswith(dom):
                    errors.append(f"match {key}: {mt[key]!r} must be {dom}…")
    lau = home.get("laundry")
    if lau is not None:
        if not isinstance(lau, dict):
            errors.append("laundry: must be a mapping (waiting:, place:, script: …)")
        else:
            if not lau.get("waiting"):
                errors.append("laundry: 'waiting' is missing (the \"Laundry waiting\" toggle)")
            for key in LAUNDRY_KEYS:
                if lau.get(key):
                    entity(f"laundry {key}", lau[key])
            if lau.get("place") and not lau.get("script"):
                errors.append("laundry: with 'place', also set 'script' (a script made from the Laundry hung blueprint)")
            if lau.get("script") and not str(lau["script"]).startswith("script."):
                errors.append(f"laundry script: {lau['script']!r} must be a script (script.…)")
    e = home.get("entry")
    if e is not None:
        if not isinstance(e, dict):
            errors.append("entry: must be a mapping (ringing:, camera:, doors: …)")
        else:
            for key in ENTRY_SINGLE:
                if e.get(key):
                    entity(f"entry {key}", e[key])
            if e.get("popup", "card") not in POPUPS:
                errors.append(f"entry popup: {e.get('popup')!r} — use card (built in, needs card-mod), browser_mod or none")
            if not e.get("ringing"):
                errors.append("entry: 'ringing' is missing (the toggle the entry_ring blueprint turns on)")
            doors = e.get("doors") or []
            if not isinstance(doors, list) or not doors:
                errors.append("entry doors: list at least one door, e.g. [{name: Building door, open: script.open_building_door}]")
            else:
                for j, door in enumerate(doors):
                    if not isinstance(door, dict) or not door.get("name") or not door.get("open"):
                        errors.append(f"entry doors[{j}]: needs a 'name' and an 'open' entity")
                        continue
                    entity(f"entry doors[{j}] ({door['name']}) open", door["open"])
                    if door.get("confirm"):
                        entity(f"entry doors[{j}] ({door['name']}) confirm", door["confirm"])
                        if str(door["confirm"]).split(".")[0] not in ("binary_sensor", "lock", "cover"):
                            errors.append(f"entry doors[{j}] ({door['name']}): 'confirm' must be a binary_sensor, lock or cover")
                    if isinstance(door["open"], str) and door["open"].split(".")[0] not in OPENERS:
                        errors.append(f"entry doors[{j}] ({door['name']}): 'open' must be a script, lock, button or cover "
                                      "(for a relay switch, use the entry_open script blueprint)")
    take = home.get("alarm_takeover")
    if take:
        if not home.get("alarm"):
            errors.append("alarm_takeover: also set 'alarm' (your alarm panel entity)")
        if isinstance(take, dict) and take.get("countdown"):
            entity("alarm_takeover countdown", take["countdown"])
            if not str(take["countdown"]).startswith("timer."):
                errors.append(f"alarm_takeover countdown: {take['countdown']!r} must be a timer (timer.…)")
    extra = home.get("extra_alerts")
    if extra is not None:
        if not isinstance(extra, list):
            errors.append("extra_alerts: must be a list of {entity, text}")
        else:
            for k, a in enumerate(extra):
                if not isinstance(a, dict) or not a.get("entity") or not a.get("text"):
                    errors.append(f"extra_alerts[{k}]: needs an 'entity' and a 'text'")
                    continue
                entity(f"extra_alerts[{k}]", a["entity"])
    rooms = home.get("rooms") or []
    if not isinstance(rooms, list):
        return errors + ["'rooms' must be a list (each item starts with '- name:')"]
    seen: dict[str, str] = {}
    for i, room in enumerate(rooms):
        if not isinstance(room, dict) or not room.get("name"):
            errors.append(f"rooms[{i}]: every room needs a 'name'")
            continue
        where = f"rooms[{i}] ({room['name']})"
        path = slug(str(room["name"]))
        if path in RESERVED:
            errors.append(f"{where}: the name clashes with the '{path}' page; pick another")
        elif path in seen:
            errors.append(f"{where}: same page address as {seen[path]}; room names must differ")
        seen.setdefault(path, where)
        for key in ROOM_SINGLE:
            if room.get(key):
                entity(f"{where} {key}", room[key])
        for key in ROOM_LISTS:
            items = room.get(key) or []
            if not isinstance(items, list):
                errors.append(f"{where} {key}: must be a list, e.g. [{key[:-1] if key != 'other' else 'switch'}.example]")
                continue
            for j, item in enumerate(items):
                entity(f"{where} {key}[{j}]", item)
    return errors


def validate(home) -> None:
    errors = check(home)
    if errors:
        sys.exit("Please fix my_home.yaml:\n  - " + "\n  - ".join(errors))


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):  # write every card out in full, no &anchors
        return True


def _str(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _str)


def write(home: dict, out: Path) -> list[Path]:
    """Write both dashboards into `out`, moving any previous ones to out/previous/."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, build in (("tablet", tablet), ("phone", phone)):
        path = out / f"{name}.yaml"
        if path.exists():
            (out / "previous").mkdir(exist_ok=True)
            path.replace(out / "previous" / path.name)
        path.write_text(yaml.dump(build(home), Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120))
        written.append(path)
    return written


CARDS = [  # (match in the rendered dashboards, card to install)
    ("custom:mushroom-", "Mushroom"),
    ("custom:clock-weather-card", "Clock Weather Card (v3 or newer)"),
    ("custom:navbar-card", "navbar-card"),
    ("custom:mod-card", "card-mod"),
    ("card_mod", "card-mod"),
    ("custom:webrtc-camera", "WebRTC Camera"),
]


def entities_in(value) -> list[str]:
    """Every entity id written in my_home.yaml, in order, once."""
    found: list[str] = []
    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and ENTITY.match(v) and v.split(".")[0] not in ("media_source",) and v not in found:
            found.append(v)
    walk(value)
    return found


def needs(home: dict) -> str:
    """What this my_home.yaml needs in Home Assistant: cards for the features it uses, and its entities."""
    text = json.dumps([tablet(home), phone(home)])
    cards = []
    for match, card in CARDS:
        if match in text and card not in cards:
            cards.append(card)
    t = home.get("tablet") or {}
    if t.get("kiosk"):
        cards.append("kiosk-mode (tablet: kiosk: true)")
    if t.get("screensaver"):
        cards.append("Wall Panel (tablet: screensaver)")
    if (home.get("entry") or {}).get("popup") == "browser_mod":
        cards.append("browser_mod (entry: popup: browser_mod)")
    ents = entities_in(home)
    probe = ("{%- set ids = " + json.dumps(ents) + " -%}\n"
             "{%- set missing = ids | reject('in', states | map(attribute='entity_id') | list) | list -%}\n"
             "{{ 'All ' ~ ids | count ~ ' entities exist.' if not missing else 'Missing: ' ~ missing | join(', ') }}")
    lines = ["Cards to install from HACS (only for the features you turned on):"]
    lines += [f"  - {c}" for c in cards] or ["  - none"]
    lines += ["", f"Entities used by my_home.yaml ({len(ents)}):"] + [f"  - {e}" for e in ents]
    lines += ["", "Check they exist: paste this in Home Assistant → Developer tools → Template:", "", probe]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    out = ROOT / "out"
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1]).resolve()
        del args[i:i + 2]
    show_needs = "--needs" in args
    args = [a for a in args if a != "--needs"]
    source = Path(args[0]) if args else ROOT / "my_home.yaml"
    if not source.exists():
        sys.exit(f"{source} not found — copy my_home.example.yaml to my_home.yaml first.")
    home = yaml.safe_load(source.read_text())
    validate(home)
    if show_needs:
        print(needs(home))
        return
    had_previous = (out / "tablet.yaml").exists()
    for path in write(home, out):
        print(f"wrote {path}")
    if had_previous:
        print(f"the previous version is in {out / 'previous'} (paste it back to undo)")


if __name__ == "__main__":
    main()
