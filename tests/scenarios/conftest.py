"""Run the kit's real blueprint files in a test Home Assistant.

Devices are plain states the test sets; the services the blueprints call
(browser_mod, notify, locks, relays) are recorded, not executed.
"""
from __future__ import annotations

import asyncio
import shutil
from datetime import timedelta
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
async def blueprints(hass: HomeAssistant):
    """Copy blueprints in, then set up automations and scripts that use them."""
    async def _setup(automations=(), scripts=None) -> None:
        for domain, items in (("automation", automations), ("script", (scripts or {}).values())):
            for item in items:
                path = item["use_blueprint"]["path"]
                target = Path(hass.config.path("blueprints", domain, path))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(REPO / "blueprints" / domain / path, target)
        assert await async_setup_component(hass, "homeassistant", {})
        if scripts:
            assert await async_setup_component(hass, "script", {"script": scripts})
        if automations:
            assert await async_setup_component(hass, "automation", {"automation": list(automations)})
        await hass.async_block_till_done()
    return _setup


async def settle(hass: HomeAssistant, rounds: int = 30) -> None:
    for _ in range(rounds):
        await asyncio.sleep(0)


@pytest.fixture
def later(hass: HomeAssistant, freezer):
    async def _later(**delta) -> None:
        await settle(hass)
        freezer.tick(timedelta(**delta))
        async_fire_time_changed(hass, dt_util.utcnow())
        await settle(hass)
    return _later
