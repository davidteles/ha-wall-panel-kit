"""Tests for tools/render.py: both outputs, navigation, bad input, regeneration."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("render", ROOT / "tools" / "render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)

ONE_ROOM = yaml.safe_load((ROOT / "examples" / "one_room.yaml").read_text())
FULL = yaml.safe_load((ROOT / "my_home.example.yaml").read_text())


def all_cards(dashboard: dict):
    """Every card in every view, including cards nested in stacks and conditionals."""
    def walk(obj):
        if isinstance(obj, dict):
            if "type" in obj:
                yield obj
            for value in obj.values():
                yield from walk(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from walk(item)
    for view in dashboard["views"]:
        yield from walk(view.get("sections", []))


def links(dashboard: dict) -> set[str]:
    found = set()
    for card in all_cards(dashboard):
        tap = card.get("tap_action") or {}
        if tap.get("action") == "navigate":
            found.add(tap["navigation_path"])
        for route in card.get("routes", []):
            found.add(route["url"])
    return found


@pytest.mark.parametrize("home", [ONE_ROOM, FULL], ids=["one_room", "full"])
@pytest.mark.parametrize("build,base", [(render.tablet, "/wall-panel"), (render.phone, "/phone-home")])
def test_every_link_points_at_a_page(home, build, base):
    dashboard = build(home)
    pages = {f"{base}/{view['path']}" for view in dashboard["views"]}
    assert links(dashboard), "expected some navigation"
    assert links(dashboard) <= pages, f"links to missing pages: {links(dashboard) - pages}"


@pytest.mark.parametrize("home", [ONE_ROOM, FULL], ids=["one_room", "full"])
def test_phone_never_gets_kiosk_or_screensaver(home):
    phone = render.phone(home)
    assert "kiosk_mode" not in phone and "wallpanel" not in phone


def test_tablet_kiosk_and_screensaver_only_when_asked():
    assert "kiosk_mode" not in render.tablet(ONE_ROOM)
    assert "wallpanel" not in render.tablet(ONE_ROOM)
    full = render.tablet(FULL)
    assert "kiosk_mode" in full and "wallpanel" in full
    # The admin toggle brings the header back.
    assert FULL["tablet"]["admin_toggle"] in full["kiosk_mode"]["hide_header"]


def test_optional_pages_appear_only_when_configured():
    paths = {v["path"] for v in render.tablet(ONE_ROOM)["views"]}
    assert {"home", "rooms", "living-room"} <= paths
    assert not {"security", "energy"} & paths
    full_paths = {v["path"] for v in render.tablet(FULL)["views"]}
    assert {"security", "energy"} <= full_paths


def test_the_examples_are_valid():
    assert render.check(ONE_ROOM) == []
    assert render.check(FULL) == []


def broken(**changes) -> dict:
    home = copy.deepcopy(ONE_ROOM)
    home.update(changes)
    return home


@pytest.mark.parametrize("home,expected", [
    (broken(weather=None), "'weather' is missing"),
    (broken(rooms=None), "'rooms' is missing"),
    (broken(rooms={"name": "Kitchen"}), "'rooms' must be a list"),
    (broken(rooms=[{"icon": "mdi:sofa"}]), "rooms[0]: every room needs a 'name'"),
    (broken(rooms=[{"name": "Rooms"}]), "rooms[0] (Rooms): the name clashes with the 'rooms' page"),
    (broken(rooms=[{"name": "Kitchen"}, {"name": "kitchen"}]), "rooms[1] (kitchen): same page address as rooms[0] (Kitchen)"),
    (broken(rooms=[{"name": "Kitchen", "lights": "light.kitchen"}]), "rooms[0] (Kitchen) lights: must be a list"),
    (broken(rooms=[{"name": "Kitchen", "lights": ["kitchen lamp"]}]), "rooms[0] (Kitchen) lights[0]: 'kitchen lamp' is not an entity id"),
    (broken(alarm="alarm panel"), "alarm: 'alarm panel' is not an entity id"),
    (broken(people=["person.alex", "Sam"]), "people[1]: 'Sam' is not an entity id"),
])
def test_bad_input_names_the_key(home, expected):
    errors = render.check(home)
    assert any(expected in e for e in errors), errors


def test_all_problems_are_reported_at_once():
    home = broken(weather=None, alarm="nope", rooms=[{"name": "Home"}, {"name": "Den", "covers": ["blind"]}])
    assert len(render.check(home)) == 4


def test_regenerating_keeps_the_previous_version(tmp_path):
    render.write(ONE_ROOM, tmp_path)
    first = (tmp_path / "tablet.yaml").read_text()
    bigger = copy.deepcopy(ONE_ROOM)
    bigger["rooms"].append({"name": "Kitchen", "lights": ["light.kitchen"]})
    render.write(bigger, tmp_path)
    assert (tmp_path / "previous" / "tablet.yaml").read_text() == first
    assert (tmp_path / "previous" / "phone.yaml").exists()
    assert "Kitchen" in (tmp_path / "tablet.yaml").read_text()


def test_output_is_valid_yaml(tmp_path):
    for path in render.write(FULL, tmp_path):
        assert yaml.safe_load(path.read_text())["views"]
