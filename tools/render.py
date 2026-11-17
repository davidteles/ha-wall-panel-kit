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
    template = (
        "{%- set ns = namespace(items=[]) -%}\n"
        f"{{%- set lbl = '{label}' -%}}"
        "{%- set ignore = (label_entities(lbl) + (label_devices(lbl) | map('device_entities') | sum(start=[]))) if lbl else [] -%}\n"
        "{%- for s in states.binary_sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'in', ['door', 'window', 'garage_door'])"
        " | selectattr('state', 'eq', 'on') | rejectattr('entity_id', 'in', ignore) -%}"
        "{%- set ns.items = ns.items + ['🚪 ' ~ s.name ~ ' is open'] -%}{%- endfor -%}\n"
        "{%- for s in states.sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'eq', 'battery')"
        " | selectattr('state', 'is_number') | rejectattr('entity_id', 'in', ignore) -%}"
        "{%- if s.state | float(100) < 15 -%}"
        "{%- set ns.items = ns.items + ['🪫 ' ~ s.name ~ ' ' ~ s.state ~ '%'] -%}{%- endif -%}{%- endfor -%}\n"
        f"{{%- set on = expand({jinja_list(lights)}) | selectattr('state', 'eq', 'on') | list | count -%}}\n"
        "{%- if states('zone.home') | int(1) == 0 and on > 0 -%}"
        "{%- set ns.items = ns.items + ['💡 ' ~ on ~ ' lights on and nobody home'] -%}{%- endif -%}\n"
        + rain_line(home)
        + "{{ ns.items | join('<br>') }}"
    )
    return {
        "type": "markdown",
        "content": template,
        "grid_options": {"columns": 12},
        "card_mod": {"style": "ha-card { border-left: 4px solid var(--warning-color) !important; }"},
    }


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


def panel_cards(home: dict) -> list[dict]:
    """Welcome greeting, note and Leaving button + countdown (from the kit's blueprints)."""
    p = panel(home)
    cards: list[dict] = []
    if p.get("last_arrival"):
        cards.append({
            "type": "markdown",
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
        "primary": f"{{{{ {count} }}}} lights on",
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
    weather = {
        "type": "custom:clock-weather-card",
        "entity": home["weather"],
        "forecast_rows": 3 if phone else 5,
        "time_format": 24,
    }
    if phone:
        weather["hide_clock"] = True
    first = [weather] + inside_range(home) + panel_cards(home) + [alert_strip(home), lights_summary(home)]
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
                      "sections": sections or home_sections(home, phone=False)})
    for room in home["rooms"]:
        views.append({"title": room["name"], "path": slug(room["name"]), "icon": room.get("icon"),
                      "type": "sections", "subview": True, "back_path": "/wall-panel/rooms",
                      "sections": room_sections(room)})
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
        sections = sections or home_sections(home, phone=True)
        sections = [{**sections[0], "cards": [bar] + sections[0]["cards"]}] + sections[1:]
        view = {"title": title, "path": path, "icon": icon, "type": "sections", "max_columns": 1,
                "sections": sections}
        if path != "home":
            view.update({"subview": True, "back_path": "/phone-home/home"})
        views.append(view)
    for room in home["rooms"]:
        sections = room_sections(room)
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
RESERVED = {"home", "rooms", "security", "energy"}


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


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    out = ROOT / "out"
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1]).resolve()
        del args[i:i + 2]
    source = Path(args[0]) if args else ROOT / "my_home.yaml"
    if not source.exists():
        sys.exit(f"{source} not found — copy my_home.example.yaml to my_home.yaml first.")
    home = yaml.safe_load(source.read_text())
    validate(home)
    had_previous = (out / "tablet.yaml").exists()
    for path in write(home, out):
        print(f"wrote {path}")
    if had_previous:
        print(f"the previous version is in {out / 'previous'} (paste it back to undo)")


if __name__ == "__main__":
    main()
