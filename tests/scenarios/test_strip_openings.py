"""The attention strip's open doors/windows, rendered in a test Home Assistant.

Same fixtures as the ha-blueprints leaving check. The rule behind
`skip_climate_devices` is exactly "the sensor's device also has a climate.*
entity", so these cover both ways it can be wrong and the ways out:

| fixture                                   | default | listed when              |
|-------------------------------------------|---------|--------------------------|
| plain window contact                      | listed  | always                   |
| thermostat's guessed "open window"        | skipped | option off               |
| car door, car has a climate entity        | skipped | option off               |
| car door, car has no climate entity       | LISTED  | (use the ignore label)   |
| real contact on a hub with a thermostat   | SKIPPED | `always_list`            |
| sensor with the ignore label              | skipped | never (ignore wins)      |

The strip lists door, window and garage_door sensors (not `opening`, which the
leaving check also counts): a gate with device class `opening` is not listed.
"""
from __future__ import annotations

import copy
import importlib.util

import pytest
import yaml
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, label_registry as lr
from homeassistant.helpers.template import Template

from .conftest import REPO

spec = importlib.util.spec_from_file_location("render", REPO / "tools" / "render.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
ONE_ROOM = yaml.safe_load((REPO / "examples" / "one_room.yaml").read_text())

PLAIN = ("binary_sensor.kitchen_window", "window", "Kitchen Window")
THERMOSTAT = ("binary_sensor.hall_thermostat_open_window", "window", "Hall Thermostat Window")
CAR_WITH_CLIMATE = ("binary_sensor.car_door", "door", "Car Door")
CAR_NO_CLIMATE = ("binary_sensor.old_car_door", "door", "Old Car Door")
HUB_CONTACT = ("binary_sensor.hub_bedroom_window", "window", "Bedroom Window")
LABELLED = ("binary_sensor.fridge_door", "door", "Fridge Door")
GATE = ("binary_sensor.side_gate", "opening", "Side Gate")
ALL = [PLAIN, THERMOSTAT, CAR_WITH_CLIMATE, CAR_NO_CLIMATE, HUB_CONTACT, LABELLED, GATE]
DEVICES = {
    "Kitchen window sensor": [PLAIN[0]],
    "Hall thermostat": [THERMOSTAT[0], "climate.hall"],
    "Car": [CAR_WITH_CLIMATE[0], "climate.car"],
    "Old car": [CAR_NO_CLIMATE[0]],
    "Hub with thermostat": [HUB_CONTACT[0], "climate.hub"],
    "Fridge": [LABELLED[0]],
    "Gate sensor": [GATE[0]],
}


@pytest.fixture
async def house(hass: HomeAssistant):
    devices, entities = dr.async_get(hass), er.async_get(hass)
    label = lr.async_get(hass).async_create("Ignore")
    for name, members in DEVICES.items():
        entry = MockConfigEntry(domain="test", title=name)
        entry.add_to_hass(hass)
        dev = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={("test", name)}, name=name)
        for entity_id in members:
            domain, object_id = entity_id.split(".")
            entities.async_get_or_create(domain, "test", object_id, suggested_object_id=object_id,
                                         config_entry=entry, device_id=dev.id)
    entities.async_update_entity(LABELLED[0], labels={label.label_id})
    hass.states.async_set("zone.home", "1")
    for entity_id, device_class, name in ALL:
        hass.states.async_set(entity_id, "on", {"device_class": device_class, "friendly_name": name})
    return label.label_id


def _open(hass: HomeAssistant, **home_keys) -> set[str]:
    home = copy.deepcopy(ONE_ROOM)
    home.update(home_keys)
    out = Template(render.alert_strip(home)["content"], hass).async_render(parse_result=False)
    return {line[len("🚪 "):-len(" is open")] for line in out.split("<br>") if line.startswith("🚪 ")}


async def test_default_rule_both_directions(hass, house):
    listed = _open(hass, ignore_label=house)
    assert listed == {PLAIN[2], CAR_NO_CLIMATE[2]}
    assert CAR_NO_CLIMATE[2] in listed, "a car without a climate entity is NOT skipped (use the ignore label)"
    assert HUB_CONTACT[2] not in listed, "a real contact on a device with a thermostat IS skipped by default"
    assert GATE[2] not in listed, "the strip does not count the 'opening' device class"


async def test_always_list_brings_a_real_contact_back(hass, house):
    listed = _open(hass, ignore_label=house, always_list=[HUB_CONTACT[0], LABELLED[0]])
    assert HUB_CONTACT[2] in listed, "always_list overrides the climate rule"
    assert LABELLED[2] not in listed, "the ignore label still wins over always_list"
    assert THERMOSTAT[2] not in listed and CAR_WITH_CLIMATE[2] not in listed


async def test_option_off_lists_every_door_and_window_except_ignored(hass, house):
    listed = _open(hass, ignore_label=house, skip_climate_devices=False)
    assert listed == {PLAIN[2], THERMOSTAT[2], CAR_WITH_CLIMATE[2], CAR_NO_CLIMATE[2], HUB_CONTACT[2]}
