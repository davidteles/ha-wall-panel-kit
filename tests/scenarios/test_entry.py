"""Entry: someone rings → pop-up + phones; Open → the door opens, everything closes."""
from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import settle

BELL, RINGING, LAST = "event.street_panel_doorbell", "input_boolean.entry_ringing", "input_datetime.entry_last_ring"
RELAY, GATE, CAMERA = "switch.intercom_door_release", "cover.gate", "camera.street_panel"


@pytest.fixture
async def entry(hass: HomeAssistant, blueprints):
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"entry_ringing": {}}})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        "entry_last_ring": {"has_date": True, "has_time": True}}})
    hass.states.async_set(BELL, "unknown", {"event_types": ["ring"], "device_class": "doorbell"})
    hass.states.async_set(RELAY, "off")
    hass.states.async_set(GATE, "closed")
    hass.states.async_set(CAMERA, "idle")
    calls = {
        "popup": async_mock_service(hass, "browser_mod", "popup"),
        "close": async_mock_service(hass, "browser_mod", "close_popup"),
        "phone": async_mock_service(hass, "notify", "phone"),
        "relay_on": async_mock_service(hass, "switch", "turn_on"),
        "relay_off": async_mock_service(hass, "switch", "turn_off"),
        "gate": async_mock_service(hass, "cover", "open_cover"),
    }
    await blueprints(
        scripts={
            "open_building_door": {"alias": "Building door", "use_blueprint": {"path": "entry/entry_open.yaml", "input": {
                "door_name": "Building door", "opener": RELAY, "pulse": 1}}},
            "open_gate": {"alias": "Gate", "use_blueprint": {"path": "entry/entry_open.yaml", "input": {
                "door_name": "Gate", "opener": GATE}}},
        },
        automations=[{"alias": "entry ring", "use_blueprint": {"path": "entry/entry_ring.yaml", "input": {
            "name": "Building door", "ring": [BELL, "binary_sensor.flat_doorbell"], "ringing": RINGING, "last_ring": LAST,
            "doors": ["script.open_building_door", "script.open_gate"], "camera": CAMERA,
            "ring_time": {"seconds": 90}, "popup_browsers": "wall-tablet, kitchen-tablet",
            "notify_action": "notify.phone", "phone_page": "/phone-home/entry"}}}],
    )
    return calls


async def ring(hass, event_type="ring", at="2026-11-19T10:00:00.000+00:00"):
    hass.states.async_set(BELL, at, {"event_types": ["ring"], "event_type": event_type, "device_class": "doorbell"})
    await settle(hass)


async def test_ring_opens_the_popup_and_notifies(hass, entry):
    await ring(hass)
    assert hass.states.get(RINGING).state == "on"
    assert hass.states.get(LAST).state not in ("unknown", "")
    popup = entry["popup"][0].data
    assert popup["browser_id"] == ["wall-tablet", "kitchen-tablet"]
    assert popup["title"] == "🔔 Building door" and popup["timeout"] == 90000
    stack = popup["content"]["cards"]
    assert stack[0] == {"type": "picture-entity", "entity": CAMERA, "camera_view": "live", "show_name": False, "show_state": False}
    names = [b["name"] for b in stack[1]["cards"]]
    assert names == ["Open building door", "Open gate", "Dismiss"]
    assert stack[1]["cards"][0]["tap_action"]["confirmation"]["text"] == "Open the building door?"
    msg = entry["phone"][0].data
    assert msg["title"] == "🔔 Someone at the building door"
    assert msg["data"]["image"] == f"/api/camera_proxy/{CAMERA}"
    assert msg["data"]["push"] == {"interruption-level": "time-sensitive"}
    assert [a["action"] for a in msg["data"]["actions"]] == ["ENTRY_OPEN_0", "ENTRY_OPEN_1"]
    assert all(a["authenticationRequired"] for a in msg["data"]["actions"]), "Face ID before opening"


async def test_phone_open_pulses_the_relay_and_closes_everything(hass, entry, later):
    await ring(hass)
    hass.bus.async_fire("mobile_app_notification_action", {"action": "ENTRY_OPEN_0"})
    await settle(hass)
    assert len(entry["relay_on"]) == 1 and entry["relay_on"][0].data["entity_id"] in ([RELAY], RELAY)
    assert not entry["relay_off"], "the relay stays on for the pulse"
    await later(seconds=1.5)
    await settle(hass)
    assert len(entry["relay_off"]) == 1
    assert hass.states.get(RINGING).state == "on", "the pop-up stays a moment after opening"
    assert entry["phone"][-1].data["title"] == "✅ Building door opened"
    assert entry["phone"][-1].data["data"]["push"] == {"interruption-level": "passive"}
    assert "actions" not in entry["phone"][-1].data["data"], "no more Open buttons"
    await later(seconds=10)
    await settle(hass)
    assert hass.states.get(RINGING).state == "off"
    assert entry["close"] and entry["close"][-1].data["browser_id"] == ["wall-tablet", "kitchen-tablet"]


async def test_popup_button_opens_the_gate(hass, entry, later):
    await ring(hass)
    await hass.services.async_call("script", "turn_on", {"entity_id": "script.open_gate"}, blocking=True)
    await settle(hass)
    assert len(entry["gate"]) == 1
    await later(seconds=11)
    await settle(hass)
    assert hass.states.get(RINGING).state == "off"


async def test_nobody_answers_the_popup_closes_after_the_ring_time(hass, entry, later):
    await ring(hass)
    await later(seconds=91)
    await settle(hass)
    assert hass.states.get(RINGING).state == "off"
    assert entry["close"], "pop-up closed"
    assert entry["phone"][-1].data.get("message") != "clear_notification", "a missed ring stays on the phone"


async def test_dismiss_on_the_dashboard_closes_the_popup(hass, entry):
    await ring(hass)
    await hass.services.async_call("input_boolean", "turn_off", {"entity_id": RINGING}, blocking=True)
    await settle(hass)
    assert entry["close"]


async def test_other_doorbell_events_and_blips_do_not_ring(hass, entry):
    hass.states.async_set(BELL, "unavailable")
    await settle(hass)
    hass.states.async_set(BELL, "2026-11-19T09:00:00.000+00:00", {"event_types": ["ring"], "event_type": "ring"})
    await settle(hass)
    assert not entry["popup"], "coming back from unavailable is not a ring"
    hass.states.async_set(BELL, "2026-11-19T09:05:00.000+00:00", {"event_types": ["ring", "motion"], "event_type": "motion"})
    await settle(hass)
    assert not entry["popup"]


async def test_binary_sensor_doorbell_rings(hass, entry):
    hass.states.async_set("binary_sensor.flat_doorbell", "off")
    await settle(hass)
    hass.states.async_set("binary_sensor.flat_doorbell", "on")
    await settle(hass)
    assert hass.states.get(RINGING).state == "on" and len(entry["popup"]) == 1


async def test_other_phone_buttons_are_ignored(hass, entry):
    await ring(hass)
    hass.bus.async_fire("mobile_app_notification_action", {"action": "LAUNDRY_DONE"})
    await settle(hass)
    assert hass.states.get(RINGING).state == "on" and not entry["relay_on"]


async def test_lock_with_open_support_uses_open(hass, blueprints):
    opened = async_mock_service(hass, "lock", "open")
    unlocked = async_mock_service(hass, "lock", "unlock")
    hass.states.async_set("lock.strike", "locked", {"supported_features": 1})
    hass.states.async_set("lock.flat", "locked", {"supported_features": 0})
    await blueprints(scripts={
        "strike": {"use_blueprint": {"path": "entry/entry_open.yaml", "input": {"opener": "lock.strike"}}},
        "flat": {"use_blueprint": {"path": "entry/entry_open.yaml", "input": {"opener": "lock.flat"}}}})
    await hass.services.async_call("script", "strike", {}, blocking=True)
    await hass.services.async_call("script", "flat", {}, blocking=True)
    assert len(opened) == 1 and len(unlocked) == 1
