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
    assert {"security", "energy", "entry"} <= full_paths


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
    (broken(entry={"doors": [{"name": "Door", "open": "script.open"}]}), "entry: 'ringing' is missing"),
    (broken(laundry={"place": "input_select.p", "script": "script.s"}), "laundry: 'waiting' is missing"),
    (broken(laundry={"waiting": "input_boolean.w", "place": "input_select.p"}), "laundry: with 'place', also set 'script'"),
    (broken(laundry={"waiting": "input_boolean.w", "place": "input_select.p", "script": "automation.x"}), "laundry script: 'automation.x' must be a script"),
    (broken(entry={"ringing": "input_boolean.r"}), "entry doors: list at least one door"),
    (broken(entry={"ringing": "input_boolean.r", "popup": "modal", "doors": [{"name": "D", "open": "script.o"}]}), "entry popup: 'modal'"),
    (broken(entry={"ringing": "input_boolean.r", "doors": [{"name": "Door"}]}), "entry doors[0]: needs a 'name' and an 'open' entity"),
    (broken(entry={"ringing": "input_boolean.r", "doors": [{"name": "Door", "open": "switch.relay"}]}),
     "entry doors[0] (Door): 'open' must be a script, lock, button or cover"),
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


def test_one_light_is_singular():
    """'1 light on', not '1 lights on', in the summary tile and the attention strip."""
    cards = list(all_cards(render.tablet(FULL)))
    summary = next(c for c in cards if c.get("secondary") == "Tap to turn all off")
    assert "'light' if n == 1 else 'lights'" in summary["primary"]
    strip = next(c for c in cards if c.get("type") == "markdown" and "nobody home" in c.get("content", ""))
    assert "' light' if on == 1 else ' lights'" in strip["content"]


ENTRY = FULL["entry"]


@pytest.mark.parametrize("build,base", [(render.tablet, "/wall-panel"), (render.phone, "/phone-home")])
def test_entry_page_and_strip(build, base):
    dash = build(FULL)
    page = next(v for v in dash["views"] if v["path"] == "entry")
    cards = list(all_cards({"views": [page]}))
    assert any(c.get("type") == "picture-entity" and c.get("camera_view") == "live" for c in cards)
    buttons = [c for c in cards if (c.get("tap_action") or {}).get("confirmation")]
    assert [b["primary"] for b in buttons][-2:] == ["Building door", "Gate"]
    assert all(b["tap_action"]["perform_action"] == "script.turn_on" for b in buttons)
    home = next(v for v in dash["views"] if v["path"] == "home")
    strip = next(c for c in all_cards({"views": [home]}) if c.get("type") == "markdown" and "nobody home" in c.get("content", ""))
    assert "🔔 Someone at the building door" in strip["content"]


@pytest.mark.parametrize("build", [render.tablet, render.phone])
def test_built_in_popup_covers_every_page_while_ringing(build):
    dash = build(FULL)
    for view in dash["views"]:
        overlays = [c for c in view["sections"][0]["cards"] if c.get("type") == "custom:mod-card"]
        assert len(overlays) == 1, f"{view['path']}: expected the entry pop-up"
        o = overlays[0]
        assert o["visibility"] == [{"condition": "state", "entity": FULL["entry"]["ringing"], "state": "on"}]
        assert "position: fixed" in o["card_mod"]["style"]["."]
        names = [c["primary"] for c in o["card"]["cards"][-1]["cards"]]
        assert names == ["Building door", "Gate", "Dismiss"]
    assert not any(c.get("primary") == "Someone at the building door" and c.get("type") == "custom:mushroom-template-card"
                   and "navigation_path" in str(c.get("tap_action")) for c in all_cards(dash)), "no extra red card"


def test_browser_mod_popup_gets_the_red_home_card_instead():
    home = copy.deepcopy(FULL)
    home["entry"]["popup"] = "browser_mod"
    dash = render.tablet(home)
    assert not any(c.get("type") == "custom:mod-card" for c in all_cards(dash))
    ring = next(c for c in all_cards(dash) if c.get("primary") == "Someone at the building door")
    assert ring["tap_action"]["navigation_path"] == "/wall-panel/entry"


def test_entry_talk_stream_uses_webrtc_with_the_microphone():
    home = copy.deepcopy(FULL)
    home["entry"]["talk_stream"] = "street_panel"
    page = next(v for v in render.tablet(home)["views"] if v["path"] == "entry")
    cam = next(c for c in all_cards({"views": [page]}) if c["type"] == "custom:webrtc-camera")
    assert cam["url"] == "street_panel" and "microphone" in cam["media"]


def test_lock_opener_uses_lock_open():
    home = copy.deepcopy(FULL)
    home["entry"]["doors"] = [{"name": "Front door", "open": "lock.front_door"}]
    page = next(v for v in render.tablet(home)["views"] if v["path"] == "entry")
    button = next(c for c in page["sections"][0]["cards"] if c.get("primary") == "Front door")
    assert button["tap_action"]["perform_action"] == "lock.open" and button["grid_options"]["columns"] == 12


def test_one_door_gives_two_wide_buttons_two_doors_three():
    home = copy.deepcopy(FULL)
    home["entry"]["doors"] = home["entry"]["doors"][:1]
    o = next(c for c in all_cards(render.tablet(home)) if c.get("type") == "custom:mod-card")
    row = o["card"]["cards"][-1]
    assert row["columns"] == 2 and [c["primary"] for c in row["cards"]] == ["Building door", "Dismiss"]
    o = next(c for c in all_cards(render.tablet(FULL)) if c.get("type") == "custom:mod-card")
    assert o["card"]["cards"][-1]["columns"] == 3


def test_quick_replies_speak_through_the_doorbell():
    home = copy.deepcopy(FULL)
    home["entry"].update(speaker="media_player.doorbell_speaker", tts="tts.home", replies=["Coming!", "Leave it at the door"])
    dash = render.tablet(home)
    o = next(c for c in all_cards(dash) if c.get("type") == "custom:mod-card")
    chips = o["card"]["cards"][2]["chips"]
    assert [c["content"] for c in chips] == ["Coming!", "Leave it at the door"]
    assert chips[0]["tap_action"] == {"action": "perform-action", "perform_action": "tts.speak", "target": {"entity_id": "tts.home"},
                                      "data": {"media_player_entity_id": "media_player.doorbell_speaker", "message": "Coming!"}}
    page = next(v for v in dash["views"] if v["path"] == "entry")
    assert any(c.get("type") == "custom:mushroom-chips-card" for c in page["sections"][0]["cards"])
    assert not any(c.get("type") == "custom:mushroom-chips-card" and "tts.speak" in str(c)
                   for c in all_cards(render.tablet(FULL))), "only when configured"


LAUNDRY = FULL["laundry"]


def laundry_cards_of(dash):
    home = next(v for v in dash["views"] if v["path"] == "home")
    return [c for c in all_cards({"views": [home]}) if "laundry" in str(c.get("visibility", "")) or "laundry" in str(c.get("tap_action", ""))]


@pytest.mark.parametrize("build", [render.tablet, render.phone])
def test_laundry_cards_on_home(build):
    cards = laundry_cards_of(build(FULL))
    names = [c.get("primary", "") for c in cards]
    assert any("Laundry ready to hang" in n for n in names)
    for name, place in (("Hung indoors", "Indoors"), ("Hung outside", "Outside")):
        b = next(c for c in cards if c.get("primary") == name)
        assert b["tap_action"]["perform_action"] == LAUNDRY["script"] and b["tap_action"]["data"] == {"place": place, "step": "hung"}
        assert b["visibility"] == [{"condition": "state", "entity": LAUNDRY["waiting"], "state": "on"}]
        assert b["grid_options"]["columns"] == 6, "both choices the same size"
    chips = next(c for c in cards if c.get("type") == "custom:mushroom-chips-card")
    nothing = chips["chips"][0]
    assert nothing["content"] == "Nothing to hang" and nothing["tap_action"]["data"] == {"place": "Not hung", "step": "hung"}
    assert nothing["tap_action"]["confirmation"], "Nothing to hang keeps its confirmation"
    assert "Laundry on the rack — where is it drying?" in names
    assert any(n.startswith("Drying {{") for n in names)
    assert "Laundry is outside — rain is coming" in names


def test_laundry_buttons_have_no_entity_and_the_icon_does_the_same():
    """A Mushroom template card with an entity toggles it when the icon is tapped: never on these."""
    for c in laundry_cards_of(render.tablet(FULL)):
        assert "entity" not in c, c.get("primary")
        if c.get("type") == "custom:mushroom-template-card":
            assert c.get("icon_tap_action") == c.get("tap_action"), c.get("primary")


def test_laundry_strip_lines():
    home = next(v for v in render.tablet(FULL)["views"] if v["path"] == "home")
    strip = next(c for c in all_cards({"views": [home]}) if c.get("type") == "markdown" and "nobody home" in c.get("content", ""))
    assert "🧺 Laundry ready to hang" in strip["content"] and "☔ Laundry is outside and rain is coming" in strip["content"]


def test_laundry_without_the_dropdown_is_one_tap_when_its_out():
    home = copy.deepcopy(FULL)
    home["laundry"] = {"waiting": "input_boolean.laundry_waiting"}
    cards = laundry_cards_of(render.tablet(home))
    assert len(cards) == 1
    assert cards[0]["tap_action"] == {"action": "perform-action", "perform_action": "input_boolean.turn_off",
                                      "target": {"entity_id": "input_boolean.laundry_waiting"}}


def test_no_laundry_section_no_laundry_cards():
    assert not laundry_cards_of(render.tablet(ONE_ROOM))


def test_recommended_choice_is_labelled_not_preselected():
    cards = laundry_cards_of(render.tablet(FULL))
    inside = next(c for c in cards if c.get("primary") == "Hung indoors")
    outside = next(c for c in cards if c.get("primary") == "Hung outside")
    # The label and the accent depend on the advice text only; nothing is selected or called until a tap.
    assert "'Recommended' if a[0] == 'indoors'" in inside["secondary"]
    assert "'Recommended' if a[0] == 'outdoors'" in outside["secondary"]
    assert "a[0] == 'outdoors'" in outside["card_mod"]["style"] and "border" in outside["card_mod"]["style"]
    for b in (inside, outside):
        assert b["tap_action"]["action"] == "perform-action" and "confirmation" not in b["tap_action"]


def test_rack_buttons_are_moves_not_answers():
    """A late tap on a 'Hung …' button can't overwrite an answer; buttons on the rack are moves."""
    cards = laundry_cards_of(render.tablet(FULL))
    for name in ("Indoors", "Outside", "Laundry is outside — rain is coming"):
        b = next(c for c in cards if c.get("primary") == name)
        assert b["tap_action"]["data"]["step"] == "move", name
    change = next(c for c in cards if str(c.get("primary", "")).startswith("Drying {{"))
    assert change["tap_action"]["data"] == {"place": "Change", "step": "move"}
