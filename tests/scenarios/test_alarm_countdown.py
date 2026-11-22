"""Alarm takeover countdown: the timer runs for the entry delay and stops when the alarm leaves pending."""
from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from homeassistant.core import HomeAssistant

from .conftest import settle

ALARM, TIMER = "alarm_control_panel.home", "timer.alarm_countdown"


@pytest.fixture
async def countdown(hass: HomeAssistant, blueprints):
    hass.states.async_set(ALARM, "armed_away")
    calls = {"start": async_mock_service(hass, "timer", "start"), "cancel": async_mock_service(hass, "timer", "cancel")}
    await blueprints(automations=[{"alias": "alarm countdown", "use_blueprint": {
        "path": "alarm_countdown.yaml", "input": {"alarm": ALARM, "countdown": TIMER, "default_delay": 45}}}])
    return calls


async def test_pending_starts_the_timer_with_the_alarms_own_delay(hass, countdown):
    hass.states.async_set(ALARM, "pending", {"delay": 30})
    await settle(hass)
    assert countdown["start"][0].data["duration"] == 30


async def test_without_a_delay_the_default_is_used(hass, countdown):
    hass.states.async_set(ALARM, "pending")
    await settle(hass)
    assert countdown["start"][0].data["duration"] == 45


@pytest.mark.parametrize("after", ["disarmed", "triggered"])
async def test_leaving_pending_stops_the_timer(hass, countdown, after):
    hass.states.async_set(ALARM, "pending", {"delay": 30})
    await settle(hass)
    hass.states.async_set(ALARM, after)
    await settle(hass)
    assert len(countdown["cancel"]) == 1
