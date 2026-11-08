#!/usr/bin/env python3
"""Build a tablet and a phone dashboard from my_home.yaml.

    python tools/render.py                      # reads my_home.yaml
    python tools/render.py my_home.example.yaml # try it with the example

Writes out/tablet.yaml and out/phone.yaml. Paste each into a new dashboard:
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
    template = (
        "{%- set ns = namespace(items=[]) -%}\n"
        "{%- for s in states.binary_sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'in', ['door', 'window', 'garage_door'])"
        " | selectattr('state', 'eq', 'on') -%}"
        "{%- set ns.items = ns.items + ['🚪 ' ~ s.name ~ ' is open'] -%}{%- endfor -%}\n"
        "{%- for s in states.sensor | selectattr('attributes.device_class', 'defined')"
        " | selectattr('attributes.device_class', 'eq', 'battery')"
        " | selectattr('state', 'is_number') -%}"
        "{%- if s.state | float(100) < 15 -%}"
        "{%- set ns.items = ns.items + ['🪫 ' ~ s.name ~ ' ' ~ s.state ~ '%'] -%}{%- endif -%}{%- endfor -%}\n"
        f"{{%- set on = expand({jinja_list(lights)}) | selectattr('state', 'eq', 'on') | list | count -%}}\n"
        "{%- if states('zone.home') | int(1) == 0 and on > 0 -%}"
        "{%- set ns.items = ns.items + ['💡 ' ~ on ~ ' lights on and nobody home'] -%}{%- endif -%}\n"
        "{{ ns.items | join('<br>') }}"
    )
    return {
        "type": "markdown",
        "content": template,
        "grid_options": {"columns": 12},
        "card_mod": {"style": "ha-card { border-left: 4px solid var(--warning-color) !important; }"},
    }


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


def home_sections(home: dict, phone: bool) -> list[dict]:
    weather = {
        "type": "custom:clock-weather-card",
        "entity": home["weather"],
        "forecast_rows": 3 if phone else 5,
        "time_format": 24,
    }
    if phone:
        weather["hide_clock"] = True
    first = [weather, alert_strip(home), lights_summary(home)]
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

def validate(home: dict) -> None:
    missing = [k for k in ("title", "weather", "rooms") if not home.get(k)]
    if missing:
        sys.exit(f"my_home.yaml is missing: {', '.join(missing)}")
    names = [slug(r.get("name", "")) for r in home["rooms"]]
    if "" in names or len(set(names)) != len(names):
        sys.exit("Every room needs a unique name.")
    reserved = {"home", "rooms", "security", "energy"} & set(names)
    if reserved:
        sys.exit(f"Room names clash with page names: {', '.join(sorted(reserved))}")


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):  # write every card out in full, no &anchors
        return True


def _str(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _str)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "my_home.yaml"
    if not source.exists():
        sys.exit(f"{source} not found — copy my_home.example.yaml to my_home.yaml first.")
    home = yaml.safe_load(source.read_text())
    validate(home)
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    for name, build in (("tablet", tablet), ("phone", phone)):
        path = out / f"{name}.yaml"
        path.write_text(yaml.dump(build(home), Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120))
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
