"""Component tests for the Home Assistant runtime."""

import asyncio
from datetime import datetime, timedelta, timezone
import inspect
from types import SimpleNamespace

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.lock import LockEntityFeature
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import enable_custom_integrations

from custom_components.home_activity_manager.const import (
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_APPLIANCE_CLASS,
    CONF_APPLIANCE_TYPE,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_CLIMATE_ENTITY,
    CONF_COVER_ENTITY,
    CONF_COVER_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_EMPTIED_ACTIONS,
    CONF_FINISH_ACTIONS,
    CONF_GROUP_ACTIONS,
    CONF_GROUP_ACTIONS,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_LOCK_LOCKED_ACTIONS,
    CONF_LOCK_UNLOCKED_ACTIONS,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_PLUG_ENTITY,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    CONF_SHUTTER_OPEN_ACTIONS,
    CONF_SHUTTER_CLOSE_ACTIONS,
    CONF_START_ACTIONS,
    DOMAIN,
)
from custom_components.home_activity_manager import (
    _async_appliance_device_id,
    _async_localize_category_defaults,
    _async_reload_entry,
    async_remove_entry,
    async_unload_entry,
)
from custom_components.home_activity_manager import runtime as runtime_module
from custom_components.home_activity_manager.appliance import ApplianceCycleDetector
from custom_components.home_activity_manager.sensor import _format_duration
from custom_components.home_activity_manager.appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_PROFILES,
)
from custom_components.home_activity_manager.runtime import ApplianceRuntime
from custom_components.home_activity_manager.binary_sensor import (
    ApplianceBinarySensor,
    ApplianceInputBinarySensor,
)
from custom_components.home_activity_manager.sensor import ApplianceSensor
from custom_components.home_activity_manager.button import (
    ClearPendingButton,
    ResetEnergyButton,
    async_setup_entry as setup_button_entry,
)
from custom_components.home_activity_manager.switch import (
    AppliancePlugSwitch,
    async_setup_entry as setup_switch_entry,
)
from custom_components.home_activity_manager.climate import ApplianceClimateProxy
from custom_components.home_activity_manager.cover import ApplianceCoverProxy
from custom_components.home_activity_manager.lock import ApplianceLockProxy


def _find_device(registry, *, identifiers):
    get_devices = getattr(registry, "async_get_devices", None)
    if get_devices is not None:
        return next(iter(get_devices(identifiers=identifiers)), None)
    devices = registry.devices
    device_entries = (
        devices.values() if hasattr(devices, "values") else devices
    )
    return next(
        (
            device
            for device in device_entries
            if identifiers <= device.identifiers
        ),
        None,
    )


@pytest.fixture
def config() -> dict[str, str]:
    return {
        CONF_POWER_ENTITY: "sensor.washer_power",
        CONF_DOOR_ENTITY: "binary_sensor.washer_door",
        CONF_PLUG_ENTITY: "switch.washer_plug",
        "name": "Washer",
        "appliance_type": "washer",
    }


async def _async_fire_deadline(runtime: ApplianceRuntime, when: datetime) -> None:
    if runtime._unsubscribe_timer is not None:
        runtime._unsubscribe_timer()
        runtime._unsubscribe_timer = None
    await runtime._async_handle_deadline(when)


def test_appliance_device_lookup_scopes_identifier_by_config_entry(
    hass, monkeypatch
):
    calls = []

    def get_device_by_identifier(identifier, config_entry_id):
        calls.append((identifier, config_entry_id))
        return SimpleNamespace(id="appliance-device")

    registry = SimpleNamespace(
        async_get_device_by_identifier=get_device_by_identifier
    )
    monkeypatch.setattr(dr, "async_get", lambda _: registry)

    assert _async_appliance_device_id(hass, "entry-123") == "appliance-device"
    assert calls == [((DOMAIN, "entry-123"), "entry-123")]


@pytest.mark.asyncio
async def test_auxiliary_switch_off_does_not_end_power_cycle(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(
        config[CONF_PLUG_ENTITY], "on", {"friendly_name": "Kitchen outlet"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "profile:washer")},
        name="Washer",
    )
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()

    assert runtime.detector.is_running
    assert runtime.detector.last_cycle_duration is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_auxiliary_power_tracks_consumption_without_changing_contact_activity(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_POWER_ENTITY: "sensor.ac_power",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_POWER_ENTITY], "200", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    assert runtime.display_power_w == 200
    assert not runtime.detector.is_running
    assert runtime._unsubscribe_timer is not None

    current_time[0] += timedelta(minutes=30)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.energy_kwh == pytest.approx(0.1)
    assert runtime._unsubscribe_timer is not None
    current_time[0] += timedelta(minutes=30)
    hass.states.async_set(config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    await hass.async_block_till_done()
    assert runtime.display_power_w == 100
    assert runtime.energy_kwh == pytest.approx(0.2)
    assert not runtime.detector.is_running

    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert runtime.detector.is_running
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_external_energy_sensor_preserves_its_total_and_handles_outages(hass):
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_ENERGY_ENTITY: "sensor.ac_energy",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "1250", {ATTR_UNIT_OF_MEASUREMENT: "Wh"})
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    assert runtime.display_energy_kwh == pytest.approx(1.25)

    hass.states.async_set(config[CONF_ENERGY_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh is None
    assert not runtime.detector.is_running

    hass.states.async_set(config[CONF_ENERGY_ENTITY], "10", {ATTR_UNIT_OF_MEASUREMENT: "invalid"})
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh is None
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "10")
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh is None
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "-1", {ATTR_UNIT_OF_MEASUREMENT: "kWh"})
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh is None

    hass.states.async_set(config[CONF_ENERGY_ENTITY], "2.5", {ATTR_UNIT_OF_MEASUREMENT: "kWh"})
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh == pytest.approx(2.5)
    await runtime.async_unload()


@pytest.mark.parametrize("replacement_state", ["on", "off", "unavailable"])
@pytest.mark.asyncio
async def test_replacing_activity_source_reconciles_the_existing_cycle(
    hass, monkeypatch, replacement_state
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.old_source",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    started_at = runtime.detector.cycle_started_at
    await runtime.async_unload()

    current_time[0] += timedelta(minutes=10)
    replacement = {**config, CONF_RUNNING_ENTITY: "binary_sensor.new_source"}
    hass.states.async_set(replacement[CONF_RUNNING_ENTITY], replacement_state)
    runtime = ApplianceRuntime(hass, entry, replacement)
    await runtime.async_setup()
    if replacement_state == "off":
        assert not runtime.detector.is_running
        assert runtime.detector.last_cycle_duration == timedelta(minutes=10)
    else:
        assert runtime.detector.cycle_started_at == started_at
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_replacing_power_source_restarts_confirmation(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(config[CONF_POWER_ENTITY], "10", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    await runtime.async_unload()

    current_time[0] += timedelta(minutes=1)
    replacement = {**config, CONF_POWER_ENTITY: "sensor.new_power"}
    hass.states.async_set(replacement[CONF_POWER_ENTITY], "10", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    runtime = ApplianceRuntime(hass, entry, replacement)
    await runtime.async_setup()
    assert not runtime.detector.is_running
    assert runtime.detector.next_deadline == current_time[0] + timedelta(seconds=15)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_replacing_power_source_does_not_display_old_sensor_reading(hass, config):
    hass.states.async_set(config[CONF_POWER_ENTITY], "10", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    await runtime.async_unload()

    replacement = {**config, CONF_POWER_ENTITY: "sensor.new_power"}
    hass.states.async_set(replacement[CONF_POWER_ENTITY], "unavailable")
    runtime = ApplianceRuntime(hass, entry, replacement)
    await runtime.async_setup()
    assert runtime.display_power_w is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_door_open_clears_pending_reminders(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config[CONF_EMPTIED_ACTIONS] = [{"action": "test.contents_removed"}]
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    emptied_actions: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", emptied_actions.append)
    await runtime.async_setup()
    runtime.pending_unload = True
    runtime.pending_reminder_count = 2
    runtime.next_pending_reminder = current_time[0] + timedelta(minutes=1)

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()

    assert runtime.door_open is True
    assert runtime.pending_unload is False
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    assert emptied_actions == [CONF_EMPTIED_ACTIONS]
    runtime.clear_pending_unload()
    assert emptied_actions == [CONF_EMPTIED_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_runtime_state_restores_after_unload(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    runtime.energy_kwh = 0.125
    runtime.pending_unload = True
    runtime.pending_reminder_count = 1
    runtime.next_pending_reminder = current_time[0] + timedelta(minutes=15)
    await runtime.async_unload()

    restored = ApplianceRuntime(hass, entry, config)
    await restored.async_setup()

    assert restored.detector.is_running
    assert restored.energy_kwh == 0.125
    assert restored.pending_unload is True
    assert restored.pending_reminder_count == 1
    assert restored.next_pending_reminder == current_time[0] + timedelta(minutes=15)
    await restored.async_unload()


@pytest.mark.asyncio
async def test_energy_integrates_power_over_elapsed_time(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(hours=1)
    await _async_fire_deadline(runtime, current_time[0])

    assert runtime.energy_kwh == pytest.approx(0.1)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_max_runtime_actions_fire_once(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config[CONF_MAX_RUNTIME_SECONDS] = 60
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    triggered: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", triggered.append)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    triggered.clear()

    current_time[0] += timedelta(seconds=59)
    await _async_fire_deadline(runtime, current_time[0])
    assert CONF_MAX_RUNTIME_ACTIONS not in triggered

    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    await _async_fire_deadline(runtime, current_time[0] + timedelta(seconds=1))

    assert triggered == [CONF_MAX_RUNTIME_ACTIONS]
    assert runtime.detector.is_running
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_pending_reminders_use_initial_delay_then_repeat_interval(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config.update(
        {
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 1,
        }
    )
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        options={
            CONF_GROUP_ACTIONS: {
                CONF_PENDING_ACTIONS: [{"service": "test.noop"}]
            }
        },
    )
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    reminders: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", lambda _key: None)

    async def record_actions(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_actions)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(minutes=1)
    await _async_fire_deadline(runtime, current_time[0])
    first_reminder_at = current_time[0] + timedelta(seconds=120)

    current_time[0] = first_reminder_at - timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == []
    current_time[0] = first_reminder_at
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS]

    current_time[0] += timedelta(seconds=299)
    await _async_fire_deadline(runtime, current_time[0])
    assert len(reminders) == 1
    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS, CONF_PENDING_ACTIONS]
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_overdue_restored_reminder_runs_once_then_resumes_interval(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config.update(
        {
            CONF_PENDING_ACTIONS: [{"service": "test.noop"}],
            CONF_PENDING_DELAY_SECONDS: 120,
            CONF_PENDING_INTERVAL_SECONDS: 300,
            CONF_PENDING_REPEATS: 2,
        }
    )
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 0,
            "next_pending_reminder": (
                current_time[0] - timedelta(minutes=10)
            ).isoformat(),
        }
    )
    runtime = ApplianceRuntime(hass, entry, config)
    reminders = []

    async def record_actions(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_actions)
    await runtime.async_setup()

    await _async_fire_deadline(runtime, current_time[0])
    await _async_fire_deadline(runtime, current_time[0])

    assert reminders == [CONF_PENDING_ACTIONS]
    assert runtime.pending_reminder_count == 1
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=300)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_unavailable_power_does_not_finish_a_cycle(hass, config, monkeypatch):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=10)
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(minutes=2)
    await _async_fire_deadline(runtime, current_time[0])

    assert runtime.detector.is_running
    assert runtime.detector.last_cycle_duration is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_remaining_estimate_decreases_during_power_outage(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.detector.cycle_started_at = current_time[0] - timedelta(minutes=2)
    runtime.detector.last_cycle_duration = timedelta(minutes=5)

    assert runtime.remaining_seconds == 180
    assert _format_duration(runtime.remaining_seconds) == "00:03:00"
    assert _format_duration(90061) == "25:01:01"

    await runtime.async_unload()


@pytest.mark.asyncio
async def test_action_failure_does_not_stop_later_actions(
    hass, config, monkeypatch
):
    config[CONF_START_ACTIONS] = [
        {"action": "test.fail"},
        {"action": "test.succeed"},
    ]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    executed: list[str] = []

    class FakeScript:
        def __init__(self, hass, sequence, name, domain, **kwargs):
            self.action = sequence[0]["action"]

        async def async_run(self, **kwargs):
            executed.append(self.action)
            if self.action == "test.fail":
                raise RuntimeError("simulated failure")

    monkeypatch.setattr(runtime_module, "Script", FakeScript)

    await runtime._run_actions(CONF_START_ACTIONS)

    assert executed == ["test.fail", "test.succeed"]


@pytest.mark.asyncio
async def test_group_actions_run_before_local_with_appliance_context(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "climate"},
        options={
            CONF_GROUP_ACTIONS: {
                CONF_START_ACTIONS: [{"action": "test.group_start"}],
                CONF_MAX_RUNTIME_ACTIONS: [{"action": "test.obsolete"}],
            }
        },
    )
    entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Suite")
    device_registry = dr.async_get(hass)
    executed: list[tuple[str, dict | None]] = []

    class FakeScript:
        def __init__(self, hass, sequence, name, domain, **kwargs):
            self.action = sequence[0]["action"]

        async def async_run(self, **kwargs):
            executed.append((self.action, kwargs.get("run_variables")))

    monkeypatch.setattr(runtime_module, "Script", FakeScript)
    hass.config.language = "ca"

    for appliance_id, appliance_type, name, area_id, source_entity in (
        (
            "ac_one",
            "air_conditioner_contact",
            "Aire condicionat estudi",
            area.id,
            "binary_sensor.ac_one",
        ),
        (
            "ac_two",
            "thermostat_climate",
            "Clima menjador",
            None,
            "climate.ac_two",
        ),
    ):
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, appliance_id)},
            name=f"Default {appliance_id}",
        )
        device_registry.async_update_device(
            device.id,
            name_by_user=name,
            area_id=area_id,
        )
        config = {
            CONF_APPLIANCE_TYPE: appliance_type,
            "_appliance_id": appliance_id,
            "name": f"Configured {appliance_id}",
            CONF_START_ACTIONS: [{"action": "test.local_start"}],
        }
        runtime = ApplianceRuntime(hass, entry, config)
        await runtime._run_actions(
            CONF_START_ACTIONS, source_entity_id=source_entity
        )

    assert executed == [
        (
            "test.group_start",
            {
                "ham_device_name": "Aire condicionat estudi",
                "ham_device_area_name": "Suite",
                "ham_source_class": "Aire condicionat",
                "ham_appliance_name": "Aire condicionat estudi",
                "ham_area_name": "Suite",
                "ham_source_entity_id": "binary_sensor.ac_one",
            },
        ),
        ("test.local_start", None),
        (
            "test.group_start",
            {
                "ham_device_name": "Clima menjador",
                "ham_device_area_name": None,
                "ham_source_class": "Termòstat",
                "ham_appliance_name": "Clima menjador",
                "ham_area_name": None,
                "ham_source_entity_id": "climate.ac_two",
            },
        ),
        ("test.local_start", None),
    ]


@pytest.mark.asyncio
async def test_group_action_renders_templates_in_service_data(hass):
    area = ar.async_get(hass).async_create("Tancaments")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "openings"},
        options={
            CONF_GROUP_ACTIONS: {
                CONF_START_ACTIONS: [
                    {
                        "action": "notify.send_message",
                        "data": {
                            "message": "Finestra oberta {{ area_name(ham_source_entity_id) }}"
                        },
                    }
                ]
            }
        },
    )
    entry.add_to_hass(hass)
    source = er.async_get(hass).async_get_or_create(
        "binary_sensor", "test", "window_contact"
    )
    er.async_get(hass).async_update_entity(source.entity_id, area_id=area.id)
    messages = []

    async def capture_message(call):
        messages.append(call.data["message"])

    hass.services.async_register("notify", "send_message", capture_message)
    runtime = ApplianceRuntime(
        hass,
        entry,
        {
            CONF_APPLIANCE_TYPE: "opening",
            CONF_APPLIANCE_CLASS: "door",
            "_appliance_id": "window",
            "name": "Finestra",
        },
    )

    await runtime._run_actions(
        CONF_START_ACTIONS, source_entity_id=source.entity_id
    )

    assert messages == ["Finestra oberta Tancaments"]


def test_group_actions_are_limited_to_supported_profile_hooks(hass):
    group_actions = {
        CONF_START_ACTIONS: [{"action": "test.start"}],
        CONF_PENDING_ACTIONS: [{"action": "test.pending"}],
        CONF_EMPTIED_ACTIONS: [{"action": "test.emptied"}],
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "large_appliances"},
        options={CONF_GROUP_ACTIONS: group_actions},
    )

    washer = ApplianceRuntime(
        hass, entry, {CONF_APPLIANCE_TYPE: "washer"}
    )
    refrigerator = ApplianceRuntime(
        hass, entry, {CONF_APPLIANCE_TYPE: "refrigerator"}
    )

    assert washer.group_actions[CONF_PENDING_ACTIONS] == group_actions[CONF_PENDING_ACTIONS]
    assert washer.group_actions[CONF_EMPTIED_ACTIONS] == group_actions[CONF_EMPTIED_ACTIONS]
    assert CONF_PENDING_ACTIONS not in refrigerator.group_actions
    assert CONF_EMPTIED_ACTIONS not in refrigerator.group_actions
    assert not refrigerator._has_actions(CONF_PENDING_ACTIONS)
    assert not refrigerator._has_actions(CONF_EMPTIED_ACTIONS)


@pytest.mark.parametrize("appliance_type", ["refrigerator", "refrigerator_switch"])
@pytest.mark.asyncio
async def test_refrigerator_profiles_run_cycle_start_and_finish_actions(
    hass, monkeypatch, appliance_type
):
    config = {CONF_APPLIANCE_TYPE: appliance_type}
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    runtime = ApplianceRuntime(hass, entry, config)
    executed: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", executed.append)
    current_time = datetime.now(timezone.utc)

    runtime._handle_cycle_events(
        [
            runtime_module.CycleEvent(
                runtime_module.CycleTransition.STARTED, current_time
            ),
            runtime_module.CycleEvent(
                runtime_module.CycleTransition.FINISHED,
                current_time + timedelta(minutes=5),
            ),
        ]
    )

    assert executed == [CONF_START_ACTIONS, CONF_FINISH_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_removing_entry_deletes_its_persistent_state(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save({"sentinel": True})

    await async_remove_entry(hass, entry)

    assert await store.async_load() is None


@pytest.mark.asyncio
async def test_config_entry_reload_and_unload_failure(hass, config, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    calls = []

    async def record_reload(_config_entries, entry_id):
        calls.append(("reload", entry_id))

    async def refuse_unload(_config_entries, _entry, _platforms):
        calls.append(("unload",))
        return False

    config_entries_type = type(hass.config_entries)
    monkeypatch.setattr(config_entries_type, "async_reload", record_reload)
    monkeypatch.setattr(
        config_entries_type, "async_unload_platforms", refuse_unload
    )

    await _async_reload_entry(hass, entry)
    assert not await async_unload_entry(hass, entry)
    assert calls == [("reload", entry.entry_id), ("unload",)]


@pytest.mark.asyncio
async def test_removing_door_sensor_clears_restored_pending_state(hass, config):
    config.pop(CONF_DOOR_ENTITY)
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 2,
            "next_pending_reminder": (
                datetime.now(timezone.utc) + timedelta(minutes=1)
            ).isoformat(),
        }
    )

    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    assert not runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_power_entity_is_unavailable_without_a_source(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    power = ApplianceSensor(
        runtime,
        entry,
        "power",
        lambda: runtime.display_power_w,
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    )

    assert not power.available
    assert power.native_value is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_power_entity_preserves_last_reading_internally_during_outage(
    hass, config
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    power = ApplianceSensor(
        runtime,
        entry,
        "power",
        lambda: runtime.display_power_w,
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
    )

    assert power.available
    assert power.native_value == 0

    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()

    assert not runtime.power_available
    assert runtime.detector.power_w is None
    assert not power.available
    assert power.native_value is None
    assert runtime.display_power_w == 0

    restored_runtime = ApplianceRuntime(hass, entry, config)
    restored_runtime._restore(runtime._export_state())
    assert restored_runtime.display_power_w == 0

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "11", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert runtime.power_available
    assert power.native_value == 11
    await runtime.async_unload()


def test_invalid_stored_energy_resets_appliance_runtime(hass, config):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.energy_kwh = 12
    runtime._last_valid_power_w = 8
    runtime.pending_unload = True
    runtime.pending_reminder_count = 3
    runtime.max_runtime_fired = True
    runtime.door_alarm_active = True

    runtime._restore({"energy_kwh": -1})

    assert runtime.energy_kwh == 0
    assert runtime._last_valid_power_w is None
    assert not runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert not runtime.max_runtime_fired
    assert not runtime.door_alarm_active


@pytest.mark.asyncio
async def test_power_entity_stays_unavailable_after_reload_during_outage(
    hass, config, enable_custom_integrations
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "42", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    power_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_power"
    )
    assert hass.states.get(power_entity_id).state == "42.0"

    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(power_entity_id).state == "unavailable"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)

    power_state = hass.states.get(power_entity_id)
    assert power_state.state == "unavailable"
    assert entry.runtime_data.display_power_w == 42
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "11", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(power_entity_id).state == "11.0"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_config_entry_loads_power_only_entities_and_unloads(
    hass, enable_custom_integrations
):
    config = {
        CONF_POWER_ENTITY: "sensor.washer_power",
        "name": "Washer",
        "appliance_type": "washer",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    profile_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "profile:washer")},
        name="Washer profile",
    )
    via_device_parameter = (
        {"via_device_id": profile_device.id}
        if "via_device_id"
        in inspect.signature(device_registry.async_get_or_create).parameters
        else {"via_device": (DOMAIN, "profile:washer")}
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Washer",
        **via_device_parameter,
    )
    category_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "category:washer")},
        name="Washer category",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    appliance_device = _find_device(
        device_registry,
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert appliance_device is not None
    assert appliance_device.via_device_id is None
    assert device_registry.async_get(profile_device.id) is None
    assert device_registry.async_get(category_device.id) is None

    registry = er.async_get(hass)
    entry_entities = [
        entity
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    ]
    unique_ids = {entity.unique_id for entity in entry_entities}
    assert unique_ids == {
        f"{entry.entry_id}_power",
        f"{entry.entry_id}_total_energy",
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_estimated_remaining",
        f"{entry.entry_id}_running",
        f"{entry.entry_id}_energy_reset",
    }
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_total_energy"
    ) is not None
    created_entity_ids = [entity.entity_id for entity in entry_entities]
    assert all(hass.states.get(entity_id) is not None for entity_id in created_entity_ids)
    for key, icon in {
        "power": "mdi:flash",
        "last_cycle_duration": "mdi:timer-check-outline",
        "estimated_remaining": "mdi:timer-sand",
    }.items():
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert hass.states.get(entity_id).attributes["icon"] == icon
    running_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    )
    assert hass.states.get(running_entity_id).attributes["icon"] == "mdi:washing-machine-off"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    remaining = {
        entity_id: hass.states.get(entity_id)
        for entity_id in created_entity_ids
        if hass.states.get(entity_id) is not None
    }
    assert set(remaining) == set(created_entity_ids)
    assert all(state.state == "unavailable" for state in remaining.values())
    assert hass.states.get(config[CONF_POWER_ENTITY]) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "localized_group_name", "localized_class_name"),
    (
        ("ca", "Grans electrodomèstics", "Washer"),
        ("es", "Grandes electrodomésticos", "Washer"),
        ("en", "Large appliances", "Washer"),
    ),
)
async def test_setup_localizes_legacy_category_defaults_without_changing_custom_names(
    hass, enable_custom_integrations, language, localized_group_name, localized_class_name
):
    hass.config.language = language
    for appliance_id in ("washer_default", "washer_custom"):
        hass.states.async_set(
            f"sensor.{appliance_id}_power",
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: "W"},
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "category": "washer",
            "appliances": [
                {
                    "id": "washer_default",
                    "data": {
                        "name": "Washer",
                        CONF_APPLIANCE_TYPE: "washer",
                        CONF_POWER_ENTITY: "sensor.washer_default_power",
                    },
                    "options": {},
                },
                {
                    "id": "washer_custom",
                    "data": {
                        "name": "Laundry room",
                        CONF_APPLIANCE_TYPE: "washer",
                        CONF_POWER_ENTITY: "sensor.washer_custom_power",
                    },
                    "options": {},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.title == localized_group_name
    assert entry.data["appliances"][0]["data"]["name"] == localized_class_name
    assert entry.data["appliances"][1]["data"]["name"] == "Laundry room"
    registry = dr.async_get(hass)
    default_device = _find_device(
        registry,
        identifiers={(DOMAIN, "washer_default")}
    )
    custom_device = _find_device(
        registry,
        identifiers={(DOMAIN, "washer_custom")}
    )
    assert default_device is not None
    assert custom_device is not None
    assert default_device.name == localized_class_name
    assert custom_device.name == "Laundry room"


def test_localize_legacy_category_defaults_preserves_custom_appliance_names(hass):
    hass.config.language = "ca"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        data={
            "category": "washer",
            "appliances": [
                {"id": "washer_default", "data": {"name": "Washer"}},
                {"id": "washer_custom", "data": {"name": "Laundry room"}},
            ],
        },
    )
    entry.add_to_hass(hass)

    _async_localize_category_defaults(hass, entry)

    assert entry.title == "Rentadora"
    assert entry.data["appliances"][0]["data"]["name"] == "Rentadora"
    assert entry.data["appliances"][1]["data"]["name"] == "Laundry room"


@pytest.mark.asyncio
async def test_category_entry_groups_appliances_without_parent_device(
    hass, enable_custom_integrations
):
    appliance_records = [
        {
            "id": appliance_id,
            "data": {
                CONF_POWER_ENTITY: f"sensor.{appliance_id}_power",
                "name": name,
                CONF_APPLIANCE_TYPE: "washer",
                CONF_APPLIANCE_CLASS: appliance_class,
            },
            "options": {},
        }
        for appliance_id, name, appliance_class in (
            ("washer_one", "Washer 1", "washer"),
            ("washer_two", "Dishwasher 2", "dishwasher"),
        )
    ]
    for record in appliance_records:
        hass.states.async_set(
            record["data"][CONF_POWER_ENTITY],
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: "W"},
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Large appliances",
        data={"category": "large_appliances", "appliances": appliance_records},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    assert entry.title == "Large appliances"
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "category:large_appliances")}
    ) is None
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "category:thermostat")}
    ) is None
    appliance_devices = [
        _find_device(
            device_registry,
            identifiers={(DOMAIN, record["id"])}
        )
        for record in appliance_records
    ]
    assert all(device is not None for device in appliance_devices)
    assert all(device.via_device_id is None for device in appliance_devices)
    assert all(device.manufacturer == "@pacmanforever" for device in appliance_devices)
    assert all(device.sw_version == "0.9.52" for device in appliance_devices)
    assert [device.model for device in appliance_devices] == [
        "Large appliances · Washer · Power sensor",
        "Large appliances · Dishwasher · Power sensor",
    ]
    assert len(entry.runtime_data) == 2

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        options_result["flow_id"], {"appliance_action": "group_actions"}
    )
    assert result["step_id"] == "group_actions"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_START_ACTIONS: [{"action": "test.group_start"}],
            CONF_FINISH_ACTIONS: [{"action": "test.group_finish"}],
        },
    )
    assert result["type"] == "create_entry"
    assert entry.options[CONF_GROUP_ACTIONS][CONF_START_ACTIONS] == [
        {"action": "test.group_start"}
    ]
    await hass.async_block_till_done()

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        options_result["flow_id"], {"appliance_action": "remove"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"appliance_id": "washer_two"}
    )
    assert result["step_id"] == "confirm_remove"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "confirm_remove_appliance"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert [record["id"] for record in entry.data["appliances"]] == ["washer_one"]
    assert entry.options[CONF_GROUP_ACTIONS][CONF_START_ACTIONS] == [
        {"action": "test.group_start"}
    ]
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "washer_two")}
    ) is None
    assert er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "washer_two_power"
    ) is None
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "category:washer")}
    ) is None

    options_result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        options_result["flow_id"], {"appliance_action": "remove"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"appliance_id": "washer_one"}
    )
    assert result["step_id"] == "confirm_remove"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "confirm_remove_appliance"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "last_appliance_removed"
    assert entry not in hass.config_entries.async_entries(DOMAIN)
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "washer_one")}
    ) is None


@pytest.mark.asyncio
async def test_thermostat_profiles_are_standalone_devices(
    hass, enable_custom_integrations
):
    profiles = (
        ("air_conditioner_contact", CONF_RUNNING_ENTITY, "binary_sensor.ac_contact"),
        ("air_conditioner_power", CONF_POWER_ENTITY, "sensor.ac_power"),
        ("thermostat_climate", CONF_CLIMATE_ENTITY, "climate.ac"),
    )
    appliance_records = []
    for index, (appliance_type, source_key, source_entity) in enumerate(profiles):
        attributes = (
            {ATTR_UNIT_OF_MEASUREMENT: "W"}
            if source_key == CONF_POWER_ENTITY
            else {}
        )
        hass.states.async_set(
            source_entity,
            "0" if source_key == CONF_POWER_ENTITY else "off",
            attributes,
        )
        appliance_records.append(
            {
                "id": f"thermostat-{index}",
                "data": {
                    CONF_APPLIANCE_TYPE: appliance_type,
                    source_key: source_entity,
                    "name": f"Thermostat {index}",
                },
                "options": {},
            },
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Thermostat",
        data={"category": "thermostat", "appliances": appliance_records},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    assert entry.title == "Climate control"
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "category:climate")}
    ) is None
    assert _find_device(
        device_registry,
        identifiers={(DOMAIN, "category:washer")}
    ) is None
    appliance_devices = [
        _find_device(
            device_registry,
            identifiers={(DOMAIN, record["id"])}
        )
        for record in appliance_records
    ]
    assert all(device is not None for device in appliance_devices)
    assert all(device.via_device_id is None for device in appliance_devices)

    assert len(entry.runtime_data) == len(profiles)
    await hass.config_entries.async_remove(entry.entry_id)


@pytest.mark.parametrize(
    ("with_power", "with_collision"),
    [(False, False), (True, False), (False, True), (True, True)],
)
@pytest.mark.asyncio
async def test_climate_appliance_exposes_optional_electrical_entities(
    hass, enable_custom_integrations, with_power, with_collision
):
    config = {
        CONF_APPLIANCE_TYPE: "thermostat_climate",
        CONF_CLIMATE_ENTITY: "climate.ac",
        CONF_ENERGY_ENTITY: "sensor.ac_energy",
        CONF_PLUG_ENTITY: "switch.ac_plug",
        "name": "Air conditioner",
    }
    if with_power:
        config[CONF_POWER_ENTITY] = "sensor.ac_power"
        hass.states.async_set(config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    hass.states.async_set(config[CONF_CLIMATE_ENTITY], "off")
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "2500", {ATTR_UNIT_OF_MEASUREMENT: "Wh"})
    hass.states.async_set(
        config[CONF_PLUG_ENTITY], "on", {"friendly_name": "Kitchen outlet"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    collision_entry = None
    collision_entity = None
    if with_collision:
        collision_entry = MockConfigEntry(domain="collision_source")
        collision_entry.add_to_hass(hass)
        collision_entity = registry.async_get_or_create(
            "sensor",
            collision_entry.domain,
            "occupied_energy_proxy_id",
            config_entry=collision_entry,
            suggested_object_id="air_conditioner_ac_energy_ham_proxy",
        )
    legacy_energy_entry = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_total_energy",
        config_entry=entry,
        suggested_object_id="air_conditioner_total_energy",
    )
    assert legacy_energy_entry.entity_id == "sensor.air_conditioner_total_energy"
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    energy_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_total_energy")
    power_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_power")
    plug_id = registry.async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_plug")
    assert energy_id is not None
    assert float(hass.states.get(energy_id).state) == pytest.approx(2.5)
    if with_collision:
        assert energy_id == "sensor.air_conditioner_total_energy"
        assert registry.async_get("sensor.air_conditioner_ac_energy_ham_proxy") == (
            collision_entity
        )
    else:
        assert energy_id == "sensor.air_conditioner_ac_energy_ham_proxy"
    reset_button_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_energy_reset"
    )
    assert (reset_button_id is not None) == with_power
    assert (power_id is not None) == with_power
    if power_id is not None:
        assert power_id == "sensor.air_conditioner_ac_power_ham_proxy"
    assert plug_id is not None
    assert plug_id == (
        "switch.air_conditioner_"
        f"{config[CONF_PLUG_ENTITY].split('.', maxsplit=1)[1]}_ham_proxy"
    )
    assert hass.states.get(plug_id).attributes["friendly_name"] == (
        "Air conditioner Kitchen outlet (HAM Proxy)"
    )
    plug_entry = registry.async_get(plug_id)
    assert plug_entry is not None
    assert plug_entry.has_entity_name is True
    assert plug_entry.original_name == "Kitchen outlet (HAM Proxy)"
    assert plug_entry.device_id is not None
    registry.async_update_entity(
        plug_id,
        has_entity_name=False,
        name="Rentadora",
        original_name="Old outlet name",
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    plug_entry = registry.async_get(plug_id)
    assert plug_entry.has_entity_name is True
    assert plug_entry.name == "Rentadora"
    assert plug_entry.original_name == "Kitchen outlet (HAM Proxy)"
    assert hass.states.get(plug_id).attributes["friendly_name"] == "Rentadora"
    if reset_button_id is not None:
        entry.runtime_data.energy_kwh = 1.25
        await hass.services.async_call(
            "button", "press", {"entity_id": reset_button_id}, blocking=True
        )
        assert entry.runtime_data.energy_kwh == 0
        assert hass.states.get(config[CONF_ENERGY_ENTITY]).state == "2500"
        assert float(hass.states.get(energy_id).state) == pytest.approx(0)
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "3000", {ATTR_UNIT_OF_MEASUREMENT: "Wh"})
    await hass.async_block_till_done()
    expected_energy = 0.5 if with_power else 3.0
    assert float(hass.states.get(energy_id).state) == pytest.approx(expected_energy)
    assert not entry.runtime_data.detector.is_running
    assert await hass.config_entries.async_unload(entry.entry_id)
    if reset_button_id is not None:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert float(hass.states.get(energy_id).state) == pytest.approx(0.5)
        assert hass.states.get(config[CONF_ENERGY_ENTITY]).state == "3000"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_external_energy_reset_waits_for_a_valid_source_reading(hass):
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_POWER_ENTITY: "sensor.ac_power",
        CONF_ENERGY_ENTITY: "sensor.ac_energy",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    hass.states.async_set(config[CONF_ENERGY_ENTITY], "unavailable")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    runtime.reset_local_energy()
    assert runtime.display_energy_kwh is None
    hass.states.async_set(
        config[CONF_ENERGY_ENTITY], "2.5", {ATTR_UNIT_OF_MEASUREMENT: "kWh"}
    )
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh == pytest.approx(0)
    hass.states.async_set(
        config[CONF_ENERGY_ENTITY], "3.0", {ATTR_UNIT_OF_MEASUREMENT: "kWh"}
    )
    await hass.async_block_till_done()
    assert runtime.display_energy_kwh == pytest.approx(0.5)
    assert hass.states.get(config[CONF_ENERGY_ENTITY]).state == "3.0"
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_external_energy_reset_baseline_is_scoped_to_its_source(hass):
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_POWER_ENTITY: "sensor.ac_power",
        CONF_ENERGY_ENTITY: "sensor.ac_energy",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    hass.states.async_set(
        config[CONF_ENERGY_ENTITY], "2.5", {ATTR_UNIT_OF_MEASUREMENT: "kWh"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    runtime.reset_local_energy()
    assert runtime.display_energy_kwh == pytest.approx(0)
    await runtime.async_unload()

    replacement_config = {**config, CONF_ENERGY_ENTITY: "sensor.ac_energy_replacement"}
    hass.states.async_set(
        replacement_config[CONF_ENERGY_ENTITY],
        "4.0",
        {ATTR_UNIT_OF_MEASUREMENT: "kWh"},
    )
    runtime = ApplianceRuntime(hass, entry, replacement_config)
    await runtime.async_setup()
    assert runtime.display_energy_kwh == pytest.approx(4.0)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_switch_activity_ignores_conflicting_auxiliary_power(hass):
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator_switch",
        CONF_PLUG_ENTITY: "switch.refrigerator",
        CONF_POWER_ENTITY: "sensor.refrigerator_power",
        CONF_DOOR_ENTITY: "binary_sensor.refrigerator_door",
        "name": "Refrigerator",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    hass.states.async_set(config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    assert runtime.detector.is_running

    hass.states.async_set(config[CONF_POWER_ENTITY], "500", {ATTR_UNIT_OF_MEASUREMENT: "W"})
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert not runtime.detector.is_running
    assert runtime.display_power_w == 500
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_optional_plug_and_pending_button_controls(
    hass, config, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config[CONF_EMPTIED_ACTIONS] = [{"action": "test.contents_removed"}]
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "100", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    runtime = entry.runtime_data
    emptied_actions: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", emptied_actions.append)

    plug_entities = []
    await setup_switch_entry(hass, entry, plug_entities.extend)
    assert len(plug_entities) == 1
    plug = plug_entities[0]
    plug.hass = hass
    assert plug.available
    assert not plug.is_on
    assert plug.icon == "mdi:power-plug-off"
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert plug.icon == "mdi:power-plug"
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert plug.icon == "mdi:power-plug-off"

    calls = []

    async def record_service_call(
        _service_registry, domain, service, service_data, blocking=False
    ):
        calls.append((domain, service, service_data, blocking))

    monkeypatch.setattr(
        type(hass.services), "async_call", record_service_call
    )
    await plug.async_turn_on()
    await plug.async_turn_off()
    assert calls == [
        ("switch", "turn_on", {"entity_id": config[CONF_PLUG_ENTITY]}, True),
        ("switch", "turn_off", {"entity_id": config[CONF_PLUG_ENTITY]}, True),
    ]

    hass.states.async_set(config[CONF_PLUG_ENTITY], "unavailable")
    assert not plug.available
    assert not plug.is_on
    assert plug.icon == "mdi:power-plug-off-outline"
    updates = []
    monkeypatch.setattr(plug, "async_write_ha_state", lambda: updates.append(True))
    plug._handle_runtime_update()
    assert updates == [True]

    button_entities = []
    await setup_button_entry(hass, entry, button_entities.extend)
    assert len(button_entities) == 2
    pending_button = next(
        button for button in button_entities if isinstance(button, ClearPendingButton)
    )
    reset_button = next(
        button for button in button_entities if isinstance(button, ResetEnergyButton)
    )
    assert reset_button.icon == "mdi:counter"
    runtime.energy_kwh = 0.25
    await reset_button.async_press()
    assert runtime.energy_kwh == 0
    assert hass.states.get(config[CONF_POWER_ENTITY]).state == "100"
    assert er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_total_energy"
    ) is not None

    runtime.pending_unload = True
    runtime.pending_reminder_count = 2
    runtime.next_pending_reminder = dt_util.utcnow() + timedelta(minutes=1)
    pending_entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_pending_unload"
    )
    runtime._notify()
    assert hass.states.get(pending_entity_id).attributes["icon"] == "mdi:bell-alert"
    await pending_button.async_press()
    assert pending_button.icon == "mdi:notification-clear-all"
    assert hass.states.get(pending_entity_id).attributes["icon"] == "mdi:bell-outline"
    assert not runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    assert emptied_actions == [CONF_EMPTIED_ACTIONS]
    store = runtime._store
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await store.async_load())["energy_kwh"] == 0


@pytest.mark.parametrize(
    ("appliance_type", "with_external_energy"),
    (
        (appliance_type, with_external_energy)
        for appliance_type in (
            "thermostat_climate",
            "air_conditioner_contact",
            "air_conditioner_power",
            "washer",
            "dishwasher",
            "dryer",
            "refrigerator",
            "refrigerator_switch",
            "aquarium_plug",
            "aquarium_power",
        )
        for with_external_energy in (False, True)
    ),
)
@pytest.mark.asyncio
async def test_local_energy_reset_button_is_available_for_power_profiles(
    hass, appliance_type, with_external_energy
):
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        CONF_POWER_ENTITY: "sensor.appliance_power",
        "name": "Appliance",
    }
    if with_external_energy:
        config[CONF_ENERGY_ENTITY] = "sensor.appliance_energy"
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    entry.runtime_data = ApplianceRuntime(hass, entry, config)

    buttons = []
    await setup_button_entry(hass, entry, buttons.extend)

    has_energy_output = with_external_energy or (
        "total_energy" in APPLIANCE_PROFILES[appliance_type].output_entities
        and bool(config.get(CONF_POWER_ENTITY))
    )
    assert len(buttons) == int(has_energy_output)
    if has_energy_output:
        assert isinstance(buttons[0], ResetEnergyButton)


@pytest.mark.asyncio
async def test_aquarium_smart_plug_exposes_local_energy_and_reset(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "aquarium_plug",
        CONF_PLUG_ENTITY: "switch.aquarium_plug",
        CONF_POWER_ENTITY: "sensor.aquarium_power",
        "name": "Aquarium",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    hass.states.async_set(
        config[CONF_POWER_ENTITY],
        "86",
        {ATTR_UNIT_OF_MEASUREMENT: "W"},
    )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_total_energy"
    ) is not None
    assert registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_energy_reset"
    ) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("appliance_type", "unique_id"),
    (
        ("washer", "clear_pending"),
        ("dishwasher", "clear_pending"),
        ("dryer", "clear_pending"),
        ("thermostat_climate", "energy_reset"),
        ("air_conditioner_contact", "energy_reset"),
        ("air_conditioner_power", "energy_reset"),
        ("washer", "energy_reset"),
        ("dishwasher", "energy_reset"),
        ("dryer", "energy_reset"),
        ("refrigerator", "energy_reset"),
        ("refrigerator_switch", "energy_reset"),
    ),
)
@pytest.mark.asyncio
async def test_obsolete_optional_buttons_are_removed_from_entity_registry(
    hass, appliance_type, unique_id
):
    config = {CONF_APPLIANCE_TYPE: appliance_type, "name": "Appliance"}
    if unique_id == "energy_reset":
        config.update(
            {
                CONF_POWER_ENTITY: None,
                CONF_ENERGY_ENTITY: "sensor.appliance_energy",
            }
        )
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    entry.runtime_data = runtime
    registry = er.async_get(hass)
    stale_entity = registry.async_get_or_create(
        "button",
        DOMAIN,
        f"{entry.entry_id}_{unique_id}",
        config_entry=entry,
    )

    buttons = []
    await setup_button_entry(hass, entry, buttons.extend)

    assert buttons == []
    assert registry.async_get(stale_entity.entity_id) is None


@pytest.mark.asyncio
async def test_restored_finish_deadline_waits_for_power_to_return(
    hass, config, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    detector = ApplianceCycleDetector()
    detector.observe_power(5, "W", current_time[0])
    detector.advance_time(current_time[0] + timedelta(seconds=15))
    detector.observe_power(0.5, "W", current_time[0] + timedelta(seconds=20))
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save({"detector": detector.export_state()})
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")

    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()
    restored_deadline = runtime.detector.next_deadline
    assert restored_deadline == current_time[0] + timedelta(seconds=80)

    current_time[0] += timedelta(minutes=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    assert runtime.detector.next_deadline == restored_deadline

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert runtime.detector.is_running
    assert runtime.detector.last_cycle_duration is None
    assert runtime.detector.next_deadline is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_contact_profile_tracks_louver_sensor_without_power_entities(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    registry = er.async_get(hass)
    running_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    )
    wrapper_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_input_running"
    )
    assert hass.states.get(running_entity_id).state == "on"
    assert wrapper_entity_id is None
    assert hass.states.get(running_entity_id).attributes["icon"] == "mdi:hvac"
    current_time[0] += timedelta(seconds=12)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration == timedelta(seconds=12)
    duration_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_last_cycle_duration"
    )
    duration_state = hass.states.get(duration_entity_id)
    assert duration_state.state == "00:00:12"
    assert ATTR_UNIT_OF_MEASUREMENT not in duration_state.attributes
    assert "device_class" not in duration_state.attributes

    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
    }
    running_state = hass.states.get(running_entity_id)
    assert running_state.state == "off"
    assert running_state.attributes["source_entity"] == config[CONF_RUNNING_ENTITY]
    assert running_state.attributes["device_class"] == "running"
    assert registry.async_get(running_entity_id).translation_key == "running"
    assert hass.states.get(running_entity_id).attributes["icon"] == "mdi:hvac-off"
    device_id = _async_appliance_device_id(hass, entry)
    assert device_id is not None
    assert registry.async_get(running_entity_id).device_id == device_id

    hass.states.async_set(config[CONF_RUNNING_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(running_entity_id).state == "unavailable"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_sun_protection_contact_tracks_position_without_running_output(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "sun_protection_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.awning_contact",
        "name": "Awning",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    position_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_input_running"
    )
    assert position_entity_id is not None
    assert position_entity_id == (
        "binary_sensor.awning_"
        f"{config[CONF_RUNNING_ENTITY].split('.', maxsplit=1)[1]}_ham_proxy"
    )
    assert hass.states.get(position_entity_id).state == "off"
    assert hass.states.get(position_entity_id).attributes["device_class"] == "opening"
    assert registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    ) is None
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    assert hass.states.get(position_entity_id).state == "on"

    current_time[0] += timedelta(seconds=12)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration == timedelta(seconds=12)
    assert hass.states.get(position_entity_id).state == "off"


@pytest.mark.asyncio
async def test_window_and_shutter_durations_are_independent_and_persisted(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "opening",
        CONF_APPLIANCE_CLASS: "window",
        CONF_RUNNING_ENTITY: "binary_sensor.window_contact",
        CONF_SHUTTER_COVER_ENTITY: "cover.window_shutter",
        "name": "Window",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closed")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    window_duration_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_last_cycle_duration"
    )
    shutter_duration_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_shutter_last_cycle_duration"
    )
    shutter_state_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_shutter"
    )
    assert window_duration_id is not None
    assert shutter_duration_id is not None
    assert shutter_state_id is not None
    assert hass.states.get(shutter_state_id).attributes["icon"] == "mdi:window-shutter"
    assert registry.async_get(window_duration_id).translation_key == "window_open_duration"
    assert registry.async_get(shutter_duration_id).translation_key == "shutter_open_duration"
    assert hass.states.get(window_duration_id).state == "unknown"
    assert hass.states.get(shutter_duration_id).state == "unknown"

    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=10)
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "opening")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=10)
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "open")
    await hass.async_block_till_done()
    assert hass.states.get(shutter_state_id).attributes["icon"] == "mdi:window-shutter-open"
    current_time[0] += timedelta(seconds=25)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert hass.states.get(window_duration_id).state == "00:00:45"

    current_time[0] += timedelta(seconds=10)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(window_duration_id).state == "00:00:45"
    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert hass.states.get(window_duration_id).state == "00:00:05"

    assert await hass.config_entries.async_unload(entry.entry_id)
    current_time[0] += timedelta(seconds=15)
    assert await hass.config_entries.async_setup(entry.entry_id)
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closing")
    await hass.async_block_till_done()
    assert entry.runtime_data.shutter_detector.is_running
    current_time[0] += timedelta(seconds=15)
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closed")
    await hass.async_block_till_done()

    assert hass.states.get(window_duration_id).state == "00:00:05"
    assert hass.states.get(shutter_duration_id).state == "00:01:10"
    assert hass.states.get(shutter_state_id).attributes["icon"] == "mdi:window-shutter"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_lock_unlock_duration_is_optional_and_persisted(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "access_contact",
        CONF_APPLIANCE_CLASS: "access",
        CONF_RUNNING_ENTITY: "binary_sensor.access_contact",
        CONF_LOCK_ENTITY: "lock.access_lock",
        "name": "Access",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locked")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    duration_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_lock_unlock_duration"
    )
    assert duration_entity_id is not None
    assert registry.async_get(duration_entity_id).translation_key == "lock_unlock_duration"
    assert hass.states.get(duration_entity_id).state == "unknown"

    hass.states.async_set(config[CONF_LOCK_ENTITY], "unlocked")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=42)
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locking")
    await hass.async_block_till_done()
    assert hass.states.get(duration_entity_id).state == "unknown"
    current_time[0] += timedelta(seconds=3)
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locked")
    await hass.async_block_till_done()
    assert hass.states.get(duration_entity_id).state == "00:00:45"

    assert await hass.config_entries.async_unload(entry.entry_id)
    current_time[0] += timedelta(seconds=10)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.states.get(duration_entity_id).state == "00:00:45"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_lock_unlock_duration_is_not_created_without_configured_lock(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "access_contact",
        CONF_APPLIANCE_CLASS: "access",
        CONF_RUNNING_ENTITY: "binary_sensor.access_contact",
        "name": "Access",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_lock_unlock_duration"
    ) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_opening_contact_tracks_position_without_running_output(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "opening",
        CONF_RUNNING_ENTITY: "binary_sensor.front_door_contact",
        "name": "Front door",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    position_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_input_running"
    )
    assert position_entity_id is not None
    assert hass.states.get(position_entity_id).state == "off"
    assert hass.states.get(position_entity_id).attributes["device_class"] == "opening"
    assert registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    ) is None
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_shutter_last_cycle_duration"
    ) is None

    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    assert hass.states.get(position_entity_id).state == "on"

    current_time[0] += timedelta(seconds=12)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration == timedelta(seconds=12)
    assert hass.states.get(position_entity_id).state == "off"


@pytest.mark.asyncio
async def test_access_contact_wrapper_is_labeled_as_open_closed_state(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "access_contact",
        CONF_APPLIANCE_CLASS: "access",
        CONF_RUNNING_ENTITY: "binary_sensor.garage_contact",
        "name": "Garage access",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    state_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_input_running"
    )
    assert state_entity_id is not None
    assert registry.async_get(state_entity_id).translation_key == "access_state"
    assert hass.states.get(state_entity_id).attributes["device_class"] == "opening"
    assert hass.states.get(state_entity_id).state == "off"

    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(state_entity_id).state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_access_cover_state_tracks_open_interval_not_motor_motion(
    hass, monkeypatch, enable_custom_integrations
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "opening_cover",
        CONF_APPLIANCE_CLASS: "access",
        CONF_COVER_ENTITY: "cover.garage_access",
        "name": "Garage access",
    }
    hass.states.async_set(config[CONF_COVER_ENTITY], "closed")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    state_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
    )
    assert state_entity_id is not None
    assert registry.async_get(state_entity_id).translation_key == "access_state"
    assert hass.states.get(state_entity_id).attributes["device_class"] == "opening"
    assert hass.states.get(state_entity_id).state == "off"

    hass.states.async_set(config[CONF_COVER_ENTITY], "opening")
    await hass.async_block_till_done()
    assert hass.states.get(state_entity_id).state == "off"
    hass.states.async_set(config[CONF_COVER_ENTITY], "open")
    await hass.async_block_till_done()
    assert hass.states.get(state_entity_id).state == "on"
    current_time[0] += timedelta(seconds=42)
    hass.states.async_set(config[CONF_COVER_ENTITY], "closing")
    await hass.async_block_till_done()
    assert hass.states.get(state_entity_id).state == "on"
    hass.states.async_set(config[CONF_COVER_ENTITY], "closed")
    await hass.async_block_till_done()

    assert hass.states.get(state_entity_id).state == "off"
    assert entry.runtime_data.detector.last_cycle_duration == timedelta(seconds=42)
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_opening_lock_and_shutter_actions_follow_stable_transitions(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "opening",
        CONF_RUNNING_ENTITY: "binary_sensor.front_door",
        CONF_LOCK_ENTITY: "lock.front_door",
        CONF_SHUTTER_CONTACT_ENTITY: "binary_sensor.front_shutter",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locked")
    hass.states.async_set(config[CONF_SHUTTER_CONTACT_ENTITY], "off")
    group_actions = {
        key: [{"action": f"test.{key}"}]
        for key in (
            CONF_START_ACTIONS,
            CONF_FINISH_ACTIONS,
            CONF_LOCK_LOCKED_ACTIONS,
            CONF_LOCK_UNLOCKED_ACTIONS,
            CONF_SHUTTER_OPEN_ACTIONS,
            CONF_SHUTTER_CLOSE_ACTIONS,
        )
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "openings"},
        options={CONF_GROUP_ACTIONS: group_actions},
    )
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions = []
    monkeypatch.setattr(
        runtime,
        "_run_actions_in_background",
        lambda key, source_entity_id=None: actions.append((key, source_entity_id)),
    )
    await runtime.async_setup()

    hass.states.async_set(config[CONF_LOCK_ENTITY], "unlocking")
    await hass.async_block_till_done()
    assert actions == []
    hass.states.async_set(config[CONF_LOCK_ENTITY], "unlocked")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locking")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_LOCK_ENTITY], "locked")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_SHUTTER_CONTACT_ENTITY], "on")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=7)
    hass.states.async_set(config[CONF_SHUTTER_CONTACT_ENTITY], "off")
    await hass.async_block_till_done()
    assert runtime.shutter_detector.last_cycle_duration == timedelta(seconds=7)
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "on")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    await hass.async_block_till_done()

    assert actions == [
        (CONF_LOCK_UNLOCKED_ACTIONS, config[CONF_LOCK_ENTITY]),
        (CONF_LOCK_LOCKED_ACTIONS, config[CONF_LOCK_ENTITY]),
        (CONF_SHUTTER_OPEN_ACTIONS, config[CONF_SHUTTER_CONTACT_ENTITY]),
        (CONF_SHUTTER_CLOSE_ACTIONS, config[CONF_SHUTTER_CONTACT_ENTITY]),
        (CONF_START_ACTIONS, config[CONF_RUNNING_ENTITY]),
        (CONF_FINISH_ACTIONS, config[CONF_RUNNING_ENTITY]),
    ]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_cover_actions_wait_for_settled_open_and_closed_states(
    hass, monkeypatch
):
    config = {
        CONF_APPLIANCE_TYPE: "opening_cover",
        CONF_COVER_ENTITY: "cover.garage_door",
    }
    hass.states.async_set(config[CONF_COVER_ENTITY], "closed")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "openings"},
        options={
            CONF_GROUP_ACTIONS: {
                CONF_START_ACTIONS: [{"action": "test.group_start"}],
                CONF_FINISH_ACTIONS: [{"action": "test.group_finish"}],
            }
        },
    )
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions = []
    monkeypatch.setattr(
        runtime,
        "_run_actions_in_background",
        lambda key, source_entity_id=None: actions.append((key, source_entity_id)),
    )
    await runtime.async_setup()

    hass.states.async_set(config[CONF_COVER_ENTITY], "opening")
    await hass.async_block_till_done()
    assert actions == []
    hass.states.async_set(config[CONF_COVER_ENTITY], "open")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_COVER_ENTITY], "closing")
    await hass.async_block_till_done()
    assert actions == [(CONF_START_ACTIONS, config[CONF_COVER_ENTITY])]
    hass.states.async_set(config[CONF_COVER_ENTITY], "closed")
    await hass.async_block_till_done()
    assert actions == [
        (CONF_START_ACTIONS, config[CONF_COVER_ENTITY]),
        (CONF_FINISH_ACTIONS, config[CONF_COVER_ENTITY]),
    ]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_associated_shutter_cover_actions_wait_for_settled_states(
    hass, monkeypatch
):
    config = {
        CONF_APPLIANCE_TYPE: "opening",
        CONF_RUNNING_ENTITY: "binary_sensor.front_door",
        CONF_SHUTTER_COVER_ENTITY: "cover.front_shutter",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closed")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"category": "openings"},
        options={
            CONF_GROUP_ACTIONS: {
                CONF_SHUTTER_OPEN_ACTIONS: [{"action": "test.shutter_open"}],
                CONF_SHUTTER_CLOSE_ACTIONS: [{"action": "test.shutter_close"}],
            }
        },
    )
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions = []
    monkeypatch.setattr(
        runtime,
        "_run_actions_in_background",
        lambda key, source_entity_id=None: actions.append((key, source_entity_id)),
    )
    await runtime.async_setup()

    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "opening")
    await hass.async_block_till_done()
    assert actions == []
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "open")
    await hass.async_block_till_done()
    assert runtime.shutter_open is True
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closing")
    await hass.async_block_till_done()
    assert len(actions) == 1
    hass.states.async_set(config[CONF_SHUTTER_COVER_ENTITY], "closed")
    await hass.async_block_till_done()

    assert actions == [
        (CONF_SHUTTER_OPEN_ACTIONS, config[CONF_SHUTTER_COVER_ENTITY]),
        (CONF_SHUTTER_CLOSE_ACTIONS, config[CONF_SHUTTER_COVER_ENTITY]),
    ]
    assert runtime.shutter_open is False
    await runtime.async_unload()


@pytest.mark.parametrize(
    ("appliance_type", "inputs", "hidden_keys", "visible_keys"),
    (
        (
            "air_conditioner_contact",
            {CONF_RUNNING_ENTITY: "binary_sensor.ac_louver"},
            ("input_running",),
            ("running",),
        ),
        (
            "opening",
            {CONF_RUNNING_ENTITY: "binary_sensor.opening_contact"},
            ("running",),
            ("input_running",),
        ),
        (
            "mailbox_motion",
            {
                CONF_MAIL_MOTION_ENTITY: "binary_sensor.mailbox_motion",
                CONF_DOOR_ENTITY: "binary_sensor.mailbox_door",
            },
            ("input_mail_motion", "input_door"),
            ("door", "pending_unload"),
        ),
        (
            "mailbox_slot",
            {
                CONF_MAIL_SLOT_ENTITY: "binary_sensor.mail_slot",
                CONF_DOOR_ENTITY: "binary_sensor.mailbox_door",
            },
            ("input_mail_slot", "input_door"),
            ("door", "mail_slot", "pending_unload"),
        ),
    ),
)
@pytest.mark.asyncio
async def test_hidden_input_wrappers_are_removed_and_outputs_remain(
    hass, appliance_type, inputs, hidden_keys, visible_keys,
    enable_custom_integrations,
):
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        **inputs,
        "name": "Test appliance",
    }
    for source_entity in inputs.values():
        hass.states.async_set(source_entity, "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    stale_entities = [
        registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            f"{entry.entry_id}_{key}",
            config_entry=entry,
        )
        for key in hidden_keys
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert all(registry.async_get(entity.entity_id) is None for entity in stale_entities)
    assert all(
        registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_{key}")
        is not None
        for key in visible_keys
    )

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("appliance_type", tuple(APPLIANCE_PROFILES))
@pytest.mark.asyncio
async def test_all_profile_inputs_are_represented_without_reassigning_sources(
    hass, appliance_type, enable_custom_integrations
):
    profile = APPLIANCE_PROFILES[appliance_type]
    if any(item.output_entity == "illuminance" for item in profile.sensor_inputs):
        hass.config.language = "ca"
    source_entry = MockConfigEntry(domain=f"source_{appliance_type}")
    source_entry.add_to_hass(hass)
    source_registry = er.async_get(hass)
    source_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={(source_entry.domain, appliance_type)},
        name=f"Source device {appliance_type}",
    )
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        "name": f"Test {appliance_type}",
    }
    input_entities = []

    for index, input_config in enumerate(profile.sensor_inputs):
        source = source_registry.async_get_or_create(
            input_config.domain,
            source_entry.domain,
            f"{appliance_type}_{index}",
            config_entry=source_entry,
            original_name=(
                None
                if input_config.output_entity == "illuminance"
                else f"Source {input_config.config_key}"
            ),
            device_id=(
                source_device.id
                if input_config.domain != "climate"
                and not input_config.proxy_always
                and index % 2 == 1
                else None
            ),
        )
        config[input_config.config_key] = source.entity_id
        input_entities.append((input_config, source.entity_id, source.device_id))

        if input_config.domain == "sensor":
            unit = "kWh" if "energy" in input_config.device_classes else "W"
            hass.states.async_set(
                source.entity_id,
                "0",
                {
                    ATTR_UNIT_OF_MEASUREMENT: unit,
                    **(
                        {"friendly_name": "Il·luminació 01 (Peixera Menjador)"}
                        if input_config.output_entity == "illuminance"
                        else {}
                    ),
                },
            )
        elif input_config.domain == "climate":
            hass.states.async_set(
                source.entity_id, "off", {"hvac_action": "idle"}
            )
        elif input_config.domain == "cover":
            hass.states.async_set(source.entity_id, "closed")
        elif input_config.domain == "lock":
            hass.states.async_set(source.entity_id, "locked")
        else:
            hass.states.async_set(source.entity_id, "off")

    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    device_id = _async_appliance_device_id(hass, entry)
    assert device_id is not None
    integration_registry = er.async_get(hass)
    if appliance_type.startswith("mailbox_"):
        status_key = "pending_unload"
    elif appliance_type in ("opening", "access_contact", "sun_protection_contact"):
        status_key = None
    else:
        status_key = "running"
    status_entity_id = (
        integration_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_{status_key}"
        )
        if status_key is not None
        else None
    )
    if status_key is None:
        assert integration_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_running"
        ) is None
    else:
        assert status_entity_id is not None
        assert integration_registry.async_get(status_entity_id).device_id == device_id

    for input_config, source_entity_id, original_device_id in input_entities:
        source = source_registry.async_get(source_entity_id)
        assert source is not None
        if input_config.domain in ("climate", "cover", "lock"):
            wrapper_id = integration_registry.async_get_entity_id(
                input_config.domain,
                DOMAIN,
                f"{entry.entry_id}_{input_config.domain}_proxy",
            )
            if original_device_id is None:
                assert source.device_id == device_id
                assert wrapper_id is None
                continue

            assert source.device_id == original_device_id
            assert wrapper_id is not None
            wrapper = integration_registry.async_get(wrapper_id)
            assert wrapper is not None
            assert wrapper.device_id == device_id
            source_name = (
                source.name
                or getattr(source, "original_name_unprefixed", None)
                or source.original_name
            )
            assert hass.states.get(wrapper_id).attributes["friendly_name"].endswith(
                f"{source_name} (HAM Proxy)"
            )
            assert wrapper_id.endswith(
                f"{source_entity_id.split('.', maxsplit=1)[1]}_ham_proxy"
            )
            assert hass.states.get(wrapper_id).attributes["source_entity"] == source_entity_id
            continue

        if not input_config.requires_source_representation:
            assert source.device_id == original_device_id
            continue

        unique_id = (
            f"{entry.entry_id}_input_{input_config.config_key.removesuffix('_entity')}"
            if input_config in profile.inputs_requiring_wrapper
            else f"{entry.entry_id}_{input_config.output_entity}"
        )
        always_proxy = input_config.proxy_always
        if original_device_id is None and not always_proxy:
            assert source.device_id == device_id
            assert integration_registry.async_get_entity_id(
                input_config.domain, DOMAIN, unique_id
            ) is None
            continue

        assert source.device_id == original_device_id
        wrapper = next(
            (
                entity
                for entity in integration_registry.entities.values()
                if entity.config_entry_id == entry.entry_id
                and entity.unique_id == unique_id
            ),
            None,
        )
        assert wrapper is not None
        if status_key is not None and input_config.output_entity == status_key:
            assert wrapper.entity_id == status_entity_id
        else:
            assert wrapper.entity_id != status_entity_id
        assert wrapper.device_id == device_id
        assert wrapper.entity_id.endswith(
            f"{source_entity_id.split('.', maxsplit=1)[1]}_ham_proxy"
        )
        wrapper_state = hass.states.get(wrapper.entity_id)
        assert wrapper_state is not None
        source_name = (
            source.name
            or getattr(source, "original_name_unprefixed", None)
            or source.original_name
        )
        if source_name is None:
            assert wrapper_state.attributes["friendly_name"].endswith(
                "Il·luminació (HAM Proxy)"
            )
        else:
            assert wrapper_state.attributes["friendly_name"].endswith(
                f"{source_name} (HAM Proxy)"
            )
        assert wrapper_state.attributes["source_entity"] == source_entity_id
        if input_config in profile.inputs_requiring_wrapper:
            assert wrapper_state.attributes["device_class"] == "opening"
        if input_config.domain in ("binary_sensor", "switch"):
            if input_config.output_entity == "running":
                continue
            for value, expected in (
                ("on", "on"),
                ("off", "off"),
                ("unknown", "unknown"),
                ("unavailable", "unavailable"),
                ("on", "on"),
            ):
                hass.states.async_set(source_entity_id, value)
                await hass.async_block_till_done()
                assert hass.states.get(wrapper.entity_id).state == expected
        elif input_config.domain == "sensor":
            unit = "kWh" if "energy" in input_config.device_classes else "W"
            for value, expected in (
                ("12", "12.0"),
                ("unknown", "unknown"),
                ("unavailable", "unavailable"),
                ("7", "7.0"),
            ):
                hass.states.async_set(
                    source_entity_id, value, {ATTR_UNIT_OF_MEASUREMENT: unit}
                )
                await hass.async_block_till_done()
                assert hass.states.get(wrapper.entity_id).state == expected

            hass.states.async_remove(source_entity_id)
            await hass.async_block_till_done()
            assert hass.states.get(wrapper.entity_id).state == "unavailable"
            if input_config.domain == "sensor":
                hass.states.async_set(
                    source_entity_id, "3", {ATTR_UNIT_OF_MEASUREMENT: unit}
                )
                expected = "3.0"
            else:
                hass.states.async_set(source_entity_id, "off")
                expected = "off"
            await hass.async_block_till_done()
            assert hass.states.get(wrapper.entity_id).state == expected

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_mailbox_slot_exposes_flap_open_and_closed_state(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "mailbox_slot",
        CONF_MAIL_SLOT_ENTITY: "binary_sensor.mail_flap",
        CONF_DOOR_ENTITY: "binary_sensor.mailbox_door",
        "name": "Mailbox",
    }
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    mail_slot_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_mail_slot"
    )
    occupied_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_pending_unload"
    )

    assert mail_slot_entity_id is not None
    assert occupied_entity_id is not None
    assert registry.async_get(occupied_entity_id).translation_key == "occupied"
    assert hass.states.get(occupied_entity_id).attributes["device_class"] == "occupancy"
    assert hass.states.get(occupied_entity_id).state == "off"
    assert hass.states.get(mail_slot_entity_id).state == "off"
    assert hass.states.get(mail_slot_entity_id).attributes["device_class"] == "door"
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-up"
    assert entry.runtime_data.door_open is False
    door_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_door"
    )
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:mailbox"

    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).state == "on"
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-open-up"
    assert hass.states.get(occupied_entity_id).state == "on"
    assert entry.runtime_data.door_open is False

    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).state == "off"
    assert hass.states.get(occupied_entity_id).state == "on"
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(mail_slot_entity_id).attributes["icon"] == "mdi:mailbox-outline"
    hass.states.async_set(config[CONF_MAIL_SLOT_ENTITY], "off")
    await hass.async_block_till_done()
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:mailbox-open"
    assert hass.states.get(occupied_entity_id).state == "off"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert entry.runtime_data.door_open is False
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_mailbox_without_main_door_still_registers_device_and_clear_button(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "mailbox_motion",
        CONF_MAIL_MOTION_ENTITY: "binary_sensor.mailbox_motion",
        "name": "Mailbox",
    }
    hass.states.async_set(config[CONF_MAIL_MOTION_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    occupied_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_pending_unload"
    )
    clear_button_entity_id = entity_registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_clear_pending"
    )
    device = _find_device(
        dr.async_get(hass), identifiers={(DOMAIN, entry.entry_id)}
    )

    assert occupied_entity_id is not None
    assert clear_button_entity_id is not None
    assert device is not None
    assert hass.states.get(occupied_entity_id).state == "off"

    hass.states.async_set(config[CONF_MAIL_MOTION_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(occupied_entity_id).state == "on"

    await hass.services.async_call(
        "button", "press", {"entity_id": clear_button_entity_id}, blocking=True
    )
    assert hass.states.get(occupied_entity_id).state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("appliance_type", "closed_icon", "open_icon"),
    (
        ("washer", "mdi:washing-machine", "mdi:washing-machine-alert"),
        ("dishwasher", "mdi:dishwasher", "mdi:dishwasher-alert"),
        ("dryer", "mdi:tumble-dryer", "mdi:tumble-dryer-alert"),
    ),
)
def test_laundry_door_icons_follow_appliance_type(
    appliance_type, closed_icon, open_icon
):
    runtime = type("Runtime", (), {"config": {CONF_APPLIANCE_TYPE: appliance_type}})()
    entry = MockConfigEntry(domain=DOMAIN, data={})
    door_open = False
    sensor = ApplianceBinarySensor(
        runtime, entry, "door", lambda: door_open
    )

    assert sensor.icon == closed_icon
    door_open = True
    assert sensor.icon == open_icon


@pytest.mark.parametrize(
    "appliance_type",
    ("thermostat_climate", "air_conditioner_contact", "air_conditioner_power"),
)
def test_air_conditioner_activity_icons_reflect_running_state(appliance_type):
    runtime = type("Runtime", (), {"config": {CONF_APPLIANCE_TYPE: appliance_type}})()
    entry = MockConfigEntry(domain=DOMAIN, data={})
    is_running = False
    sensor = ApplianceBinarySensor(runtime, entry, "running", lambda: is_running)

    assert sensor.icon == "mdi:hvac-off"
    is_running = True
    assert sensor.icon == "mdi:hvac"


@pytest.mark.parametrize("cover_state", ("open", "opening", "closing", "closed"))
def test_sun_protection_cover_running_sensor_availability(hass, cover_state):
    cover_entity_id = "cover.sun_protection"
    hass.states.async_set(cover_entity_id, cover_state)
    runtime = SimpleNamespace(
        config={
            CONF_APPLIANCE_TYPE: "sun_protection_cover",
            CONF_APPLIANCE_CLASS: "awning",
            CONF_COVER_ENTITY: cover_entity_id,
        },
        profile=APPLIANCE_PROFILES["sun_protection_cover"],
    )
    sensor = ApplianceBinarySensor(
        runtime,
        MockConfigEntry(domain=DOMAIN),
        "running",
        lambda: False,
        BinarySensorDeviceClass.OPENING,
    )
    sensor.hass = hass

    assert sensor._attr_translation_key == "awning_state"
    assert sensor._attr_device_class == BinarySensorDeviceClass.OPENING
    assert sensor.available


@pytest.mark.parametrize(
    ("appliance_type", "source_key"),
    (
        ("mailbox_motion", CONF_MAIL_MOTION_ENTITY),
        ("mailbox_slot", CONF_MAIL_SLOT_ENTITY),
    ),
)
@pytest.mark.asyncio
async def test_mailbox_arrival_actions_pending_reminders_and_door_clear(
    hass, monkeypatch, appliance_type, source_key
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        source_key: f"binary_sensor.{appliance_type}_trigger",
        CONF_DOOR_ENTITY: f"binary_sensor.{appliance_type}_door",
        CONF_START_ACTIONS: [{"action": "test.mail_arrived"}],
        CONF_FINISH_ACTIONS: [{"action": "test.mail_collected"}],
        CONF_EMPTIED_ACTIONS: [{"action": "test.contents_removed"}],
        CONF_PENDING_ACTIONS: [{"action": "test.mail_reminder"}],
        CONF_PENDING_DELAY_SECONDS: 10,
        CONF_PENDING_INTERVAL_SECONDS: 20,
        CONF_PENDING_REPEATS: 1,
        "name": "Mailbox",
    }
    hass.states.async_set(config[source_key], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    transitions: list[str] = []
    reminders: list[str] = []

    monkeypatch.setattr(runtime, "_run_actions_in_background", transitions.append)

    async def record_reminder(key: str) -> None:
        reminders.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_reminder)
    await runtime.async_setup()

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[source_key], "on")
    await hass.async_block_till_done()
    assert transitions == [CONF_START_ACTIONS]
    assert runtime.pending_unload
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=10)

    hass.states.async_set(config[source_key], "off")
    await hass.async_block_till_done()
    hass.states.async_set(config[source_key], "on")
    await hass.async_block_till_done()
    assert transitions == [CONF_START_ACTIONS]
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=10)

    current_time[0] += timedelta(seconds=10)
    await _async_fire_deadline(runtime, current_time[0])
    assert reminders == [CONF_PENDING_ACTIONS]
    assert runtime.pending_reminder_count == 1

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.pending_unload
    assert runtime.next_pending_reminder is None
    assert transitions == [CONF_START_ACTIONS, CONF_FINISH_ACTIONS, CONF_EMPTIED_ACTIONS]

    hass.states.async_set(config[source_key], "off")
    await hass.async_block_till_done()
    hass.states.async_set(config[source_key], "on")
    await hass.async_block_till_done()
    assert transitions == [
        CONF_START_ACTIONS,
        CONF_FINISH_ACTIONS,
        CONF_EMPTIED_ACTIONS,
        CONF_START_ACTIONS,
    ]
    assert runtime.pending_unload
    assert runtime.pending_reminder_count == 0
    assert runtime.next_pending_reminder is None
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert runtime.next_pending_reminder == current_time[0] + timedelta(seconds=10)
    await runtime.async_unload()


@pytest.mark.parametrize(
    ("appliance_type", "source_key"),
    (
        ("mailbox_motion", CONF_MAIL_MOTION_ENTITY),
        ("mailbox_slot", CONF_MAIL_SLOT_ENTITY),
    ),
)
@pytest.mark.asyncio
async def test_mailbox_starting_with_active_trigger_does_not_report_arrival(
    hass, monkeypatch, appliance_type, source_key
):
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        source_key: f"binary_sensor.{appliance_type}_trigger",
        CONF_DOOR_ENTITY: f"binary_sensor.{appliance_type}_door",
        CONF_START_ACTIONS: [{"action": "test.mail_arrived"}],
        "name": "Mailbox",
    }
    hass.states.async_set(config[source_key], "on")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    arrivals: list[str] = []
    monkeypatch.setattr(runtime, "_run_actions_in_background", arrivals.append)
    await runtime.async_setup()

    assert arrivals == []
    assert not runtime.pending_unload
    assert runtime.next_pending_reminder is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_refrigerator_creates_only_its_declared_entities(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    store = runtime_module.Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    await store.async_save(
        {
            "pending_unload": True,
            "pending_reminder_count": 2,
            "next_pending_reminder": (
                dt_util.utcnow() + timedelta(minutes=1)
            ).isoformat(),
        }
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.pending_unload

    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_power",
        f"{entry.entry_id}_total_energy",
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
        f"{entry.entry_id}_door",
        f"{entry.entry_id}_energy_reset",
    }
    door_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_door"
    )
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge-alert"
    hass.states.async_set(config[CONF_DOOR_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(door_entity_id).attributes["icon"] == "mdi:fridge-alert-outline"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_unassigned_appliance_plug_is_attached_without_duplicate(
    hass, enable_custom_integrations
):
    source_entry = MockConfigEntry(domain="plug_source")
    source_entry.add_to_hass(hass)
    source_entity = er.async_get(hass).async_get_or_create(
        "switch",
        source_entry.domain,
        "aquarium_plug",
        config_entry=source_entry,
        original_name="Aquarium outlet",
    )
    hass.states.async_set(source_entity.entity_id, "on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "aquarium_plug",
            CONF_PLUG_ENTITY: source_entity.entity_id,
            "name": "Aquarium",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    device_id = _async_appliance_device_id(hass, entry)
    assert device_id is not None
    assert er.async_get(hass).async_get(source_entity.entity_id).device_id == device_id
    assert er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_plug"
    ) is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(source_entity.entity_id).device_id is None


@pytest.mark.asyncio
async def test_smart_switch_refrigerator_creates_only_its_declared_entities(
    hass, enable_custom_integrations
):
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator_switch",
        CONF_PLUG_ENTITY: "switch.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        "name": "Smart-switch refrigerator",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    registry = er.async_get(hass)
    unique_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert unique_ids == {
        f"{entry.entry_id}_last_cycle_duration",
        f"{entry.entry_id}_running",
        f"{entry.entry_id}_door",
        f"{entry.entry_id}_plug",
    }
    plug_entity_id = registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_plug"
    )
    assert hass.states.get(plug_entity_id).attributes["source_entity"] == config[
        CONF_PLUG_ENTITY
    ]
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_smart_switch_refrigerator_tracks_switch_and_door_actions(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator_switch",
        CONF_PLUG_ENTITY: "switch.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Smart-switch refrigerator",
    }
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    alarms: list[str] = []

    async def record_alarm(key: str) -> None:
        alarms.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_alarm)
    await runtime.async_setup()
    await hass.async_block_till_done()
    assert not runtime.detector.is_running
    assert alarms == []
    assert not runtime.power_available
    assert runtime.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=5)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert runtime.detector.is_running
    assert runtime.detector.cycle_started_at == current_time[0]

    current_time[0] += timedelta(seconds=8)
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert not runtime.detector.is_running
    assert runtime.detector.last_cycle_duration == timedelta(seconds=8)
    assert not runtime.compressor_alarm_active

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert alarms == [
        CONF_START_ACTIONS,
        CONF_FINISH_ACTIONS,
        CONF_DOOR_OPEN_ACTIONS,
    ]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_refrigerator_door_alarm_repeats_rearms_and_persists(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        options={
            CONF_GROUP_ACTIONS: {
                CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}]
            }
        },
    )
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    assert runtime.next_compressor_alarm is None

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.pending_unload
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]
    current_time[0] += timedelta(seconds=2)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]

    await runtime.async_unload()
    restored = ApplianceRuntime(hass, entry, config)
    monkeypatch.setattr(restored, "_run_actions", record_action)
    await restored.async_setup()
    assert restored.door_alarm_fired_count == 1
    assert restored.compressor_alarm_fired_count == 0
    assert restored.next_door_alarm == current_time[0] + timedelta(seconds=1)
    assert restored.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=1)
    await _async_fire_deadline(restored, current_time[0])
    assert actions[-1] == CONF_DOOR_OPEN_ACTIONS
    assert restored.next_door_alarm is None
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    await hass.async_block_till_done()
    assert not restored.door_alarm_active
    assert restored.door_alarm_fired_count == 0
    await restored.async_unload()


@pytest.mark.asyncio
async def test_plug_off_alarm_fires_immediately_when_setup_starts_off(
    hass, monkeypatch
):
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_PLUG_ENTITY: "switch.ac_plug",
        CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off_alarm"}],
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    await hass.async_block_till_done()

    assert actions == [CONF_PLUG_OFF_ACTIONS]
    assert runtime.plug_off_alarm_fired_count == 1
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_plug_off_alarm_repeats_pauses_persists_and_rearms(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "air_conditioner_contact",
        CONF_RUNNING_ENTITY: "binary_sensor.ac_louver",
        CONF_PLUG_ENTITY: "switch.ac_plug",
        CONF_PLUG_OFF_ACTIONS: [{"action": "test.plug_off_alarm"}],
        CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS: 10,
        CONF_PLUG_OFF_REPEAT_COUNT: 1,
        "name": "Air conditioner",
    }
    hass.states.async_set(config[CONF_RUNNING_ENTITY], "off")
    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    monkeypatch.setattr(runtime, "_schedule_deadline", lambda: None)

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    assert runtime.plug_off_alarm_active
    assert runtime.next_plug_off_alarm == current_time[0]
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS]
    assert runtime.plug_off_alarm_fired_count == 1
    assert runtime.next_plug_off_alarm == current_time[0] + timedelta(seconds=10)

    restored = ApplianceRuntime(hass, entry, config)
    restored._restore(runtime._export_state())
    assert restored.plug_off_alarm_active
    assert restored.plug_off_alarm_fired_count == 1
    assert restored.next_plug_off_alarm == runtime.next_plug_off_alarm

    hass.states.async_set(config[CONF_PLUG_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=20)
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS]

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [CONF_PLUG_OFF_ACTIONS, CONF_PLUG_OFF_ACTIONS]
    assert runtime.next_plug_off_alarm is None

    hass.states.async_set(config[CONF_PLUG_ENTITY], "on")
    await hass.async_block_till_done()
    assert not runtime.plug_off_alarm_active
    assert runtime.plug_off_alarm_fired_count == 0
    assert runtime.next_plug_off_alarm is None

    hass.states.async_set(config[CONF_PLUG_ENTITY], "off")
    await hass.async_block_till_done()
    await runtime._run_alarm_if_due("plug_off", current_time[0])
    assert actions == [
        CONF_PLUG_OFF_ACTIONS,
        CONF_PLUG_OFF_ACTIONS,
        CONF_PLUG_OFF_ACTIONS,
    ]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_unassigned_climate_source_is_attached_and_tracked(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "air_conditioner", config_entry=climate_entry
    )
    replacement_entry = MockConfigEntry(domain="climate_source")
    replacement_entry.add_to_hass(hass)
    replacement_climate = er.async_get(hass).async_get_or_create(
        "climate", replacement_entry.domain, "replacement", config_entry=replacement_entry
    )
    hass.states.async_set(
        climate_entity.entity_id, "cool", {"hvac_action": "cooling"}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
            "name": "Air conditioner",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    device_id = _async_appliance_device_id(hass, entry)
    assert device_id is not None
    registered_climate = er.async_get(hass).async_get(climate_entity.entity_id)
    assert registered_climate is not None
    assert registered_climate.config_entry_id == climate_entry.entry_id
    assert registered_climate.device_id == device_id
    proxy_entity_id = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"{entry.entry_id}_climate_proxy"
    )
    assert proxy_entity_id is None
    assert entry.runtime_data.detector.is_running

    hass.states.async_set(
        climate_entity.entity_id, "cool", {"hvac_action": "idle"}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running

    hass.states.async_set(
        climate_entity.entity_id, "off", {"hvac_action": "idle"}
    )
    await hass.async_block_till_done()
    assert not entry.runtime_data.detector.is_running
    assert entry.runtime_data.detector.last_cycle_duration is not None

    hass.states.async_set(climate_entity.entity_id, "cool")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running
    hass.states.async_set(climate_entity.entity_id, "unavailable")
    await hass.async_block_till_done()
    assert entry.runtime_data.detector.is_running

    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id == device_id

    appliance_record = dict(entry.data["appliances"][0])
    appliance_data = dict(appliance_record["data"])
    appliance_data[CONF_CLIMATE_ENTITY] = replacement_climate.entity_id
    appliance_record["data"] = appliance_data
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "appliances": [appliance_record]},
    )
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None
    assert er.async_get(hass).async_get(replacement_climate.entity_id).device_id == device_id
    assert (
        er.async_get(hass).async_get_entity_id(
            "climate", DOMAIN, f"{entry.entry_id}_climate_proxy"
        )
        is None
    )

    appliance_record = dict(entry.data["appliances"][0])
    appliance_data = dict(appliance_record["data"])
    appliance_data.pop(CONF_CLIMATE_ENTITY)
    appliance_record["data"] = appliance_data
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "appliances": [appliance_record]},
    )
    await hass.async_block_till_done()
    assert CONF_CLIMATE_ENTITY not in entry.runtime_data[entry.entry_id].config
    assert er.async_get(hass).async_get(replacement_climate.entity_id).device_id is None
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None
    assert (
        er.async_get(hass).async_get_entity_id(
            "climate", DOMAIN, f"{entry.entry_id}_climate_proxy"
        )
        is None
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(replacement_climate.entity_id).device_id is None
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id is None
    assert er.async_get(hass).async_get(climate_entity.entity_id).config_entry_id == climate_entry.entry_id


@pytest.mark.asyncio
async def test_domain_proxies_mirror_source_features_and_forward_actions(
    hass, monkeypatch
):
    climate_entity_id = "climate.original_ac"
    cover_entity_id = "cover.original_blind"
    lock_entity_id = "lock.original_door"
    hass.states.async_set(
        climate_entity_id,
        "cool",
        {
            "hvac_action": "cooling",
            "hvac_modes": ["off", "cool", "invalid"],
            "current_temperature": 21.5,
            "temperature": 23,
            "target_temp_low": 19,
            "target_temp_high": 25,
            "current_humidity": 45,
            "target_humidity": 55,
            "min_temp": 10,
            "max_temp": 32,
            "min_humidity": 20,
            "max_humidity": 80,
            "target_temp_step": 0.5,
            "preset_mode": "eco",
            "preset_modes": ["eco", 1],
            "fan_mode": "quiet",
            "fan_modes": ["quiet", 1],
            "swing_mode": "on",
            "swing_modes": ["on"],
            "swing_horizontal_mode": "left",
            "swing_horizontal_modes": ["left"],
            "temperature_unit": "°C",
            "supported_features": int(ClimateEntityFeature.TARGET_TEMPERATURE),
        },
    )
    hass.states.async_set(
        cover_entity_id,
        "open",
        {
            "device_class": "blind",
            "current_position": 72,
            "current_tilt_position": 35,
            "supported_speeds": ["slow", "fast", 1],
            "supported_features": int(
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.SET_POSITION
            ),
        },
    )
    hass.states.async_set(
        lock_entity_id,
        "locked",
        {
            "code_format": r"^\d{4}$",
            "changed_by": "keypad",
            "supported_features": int(LockEntityFeature.OPEN),
        },
    )
    climate_runtime = SimpleNamespace(
        hass=hass,
        config={
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: climate_entity_id,
        },
    )
    cover_runtime = SimpleNamespace(
        hass=hass,
        config={
            CONF_APPLIANCE_TYPE: "sun_protection_cover",
            CONF_COVER_ENTITY: cover_entity_id,
        },
    )
    lock_runtime = SimpleNamespace(
        hass=hass,
        config={CONF_APPLIANCE_TYPE: "opening", CONF_LOCK_ENTITY: lock_entity_id},
    )
    climate_entry = MockConfigEntry(domain=DOMAIN, title="AC")
    cover_entry = MockConfigEntry(domain=DOMAIN, title="Blind")
    lock_entry = MockConfigEntry(domain=DOMAIN, title="Door")
    climate = ApplianceClimateProxy(climate_runtime, climate_entry)
    cover = ApplianceCoverProxy(cover_runtime, cover_entry)
    lock = ApplianceLockProxy(lock_runtime, lock_entry)
    climate.hass = cover.hass = lock.hass = hass

    assert climate.suggested_object_id == "original_ac_ham_proxy"
    assert cover.suggested_object_id == "original_blind_ham_proxy"
    assert lock.suggested_object_id == "original_door_ham_proxy"
    assert climate.hvac_mode is HVACMode.COOL
    assert [mode.value for mode in climate.hvac_modes] == ["off", "cool"]
    assert climate.hvac_action.value == "cooling"
    assert climate.native_temperature_unit.value == "°C"
    assert climate.native_current_temperature == 21.5
    assert climate.native_target_temperature == 23
    assert climate.native_target_temperature_low == 19
    assert climate.native_target_temperature_high == 25
    assert climate.current_humidity == 45
    assert climate.target_humidity == 55
    assert climate.min_temp == 10
    assert climate.max_temp == 32
    assert climate.min_humidity == 20
    assert climate.max_humidity == 80
    assert climate.target_temperature_step == 0.5
    assert climate.preset_mode == "eco"
    assert climate.preset_modes == ["eco"]
    assert climate.fan_mode == "quiet"
    assert climate.fan_modes == ["quiet"]
    assert climate.swing_mode == "on"
    assert climate.swing_modes == ["on"]
    assert climate.swing_horizontal_mode == "left"
    assert climate.swing_horizontal_modes == ["left"]
    assert climate.extra_state_attributes["source_entity"] == climate_entity_id
    assert climate.supported_features == ClimateEntityFeature.TARGET_TEMPERATURE
    assert cover.device_class.value == "blind"
    assert cover.is_closed is False
    assert cover.is_opening is False
    assert cover.is_closing is False
    assert cover.current_cover_position == 72
    assert cover.current_cover_tilt_position == 35
    assert cover.supported_speeds == ["slow", "fast"]
    assert cover.extra_state_attributes["source_entity"] == cover_entity_id
    assert cover.supported_features == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    assert lock.is_locked
    assert lock.is_locking is False
    assert lock.is_unlocking is False
    assert lock.is_open is False
    assert lock.is_opening is False
    assert lock.is_jammed is False
    assert lock.changed_by == "keypad"
    assert lock.code_format == r"^\d{4}$"
    assert lock.extra_state_attributes["source_entity"] == lock_entity_id
    assert lock.supported_features == LockEntityFeature.OPEN

    calls = []

    async def record_service_call(
        _service_registry, domain, service, service_data, blocking=False
    ):
        calls.append((domain, service, service_data, blocking))

    monkeypatch.setattr(type(hass.services), "async_call", record_service_call)
    await climate.async_set_hvac_mode(HVACMode.OFF)
    await climate.async_set_temperature(temperature=22)
    await climate.async_set_humidity(50)
    await climate.async_set_fan_mode("auto")
    await climate.async_set_preset_mode("comfort")
    await climate.async_set_swing_mode("off")
    await climate.async_set_swing_horizontal_mode("right")
    await climate.async_turn_on()
    await climate.async_turn_off()
    await cover.async_open_cover()
    await cover.async_stop_cover()
    await cover.async_set_cover_position(position=40)
    await cover.async_close_cover()
    await cover.async_open_cover_tilt()
    await cover.async_close_cover_tilt()
    await cover.async_set_cover_tilt_position(tilt_position=50)
    await cover.async_stop_cover_tilt()
    await lock.async_unlock(code="1234")
    await lock.async_lock()
    await lock.async_open()

    assert calls == [
        ("climate", "set_hvac_mode", {"hvac_mode": HVACMode.OFF, "entity_id": climate_entity_id}, True),
        ("climate", "set_temperature", {"temperature": 22, "entity_id": climate_entity_id}, True),
        ("climate", "set_humidity", {"humidity": 50, "entity_id": climate_entity_id}, True),
        ("climate", "set_fan_mode", {"fan_mode": "auto", "entity_id": climate_entity_id}, True),
        ("climate", "set_preset_mode", {"preset_mode": "comfort", "entity_id": climate_entity_id}, True),
        ("climate", "set_swing_mode", {"swing_mode": "off", "entity_id": climate_entity_id}, True),
        ("climate", "set_swing_horizontal_mode", {"swing_horizontal_mode": "right", "entity_id": climate_entity_id}, True),
        ("climate", "turn_on", {"entity_id": climate_entity_id}, True),
        ("climate", "turn_off", {"entity_id": climate_entity_id}, True),
        ("cover", "open_cover", {"entity_id": cover_entity_id}, True),
        ("cover", "stop_cover", {"entity_id": cover_entity_id}, True),
        ("cover", "set_cover_position", {"position": 40, "entity_id": cover_entity_id}, True),
        ("cover", "close_cover", {"entity_id": cover_entity_id}, True),
        ("cover", "open_cover_tilt", {"entity_id": cover_entity_id}, True),
        ("cover", "close_cover_tilt", {"entity_id": cover_entity_id}, True),
        ("cover", "set_cover_tilt_position", {"tilt_position": 50, "entity_id": cover_entity_id}, True),
        ("cover", "stop_cover_tilt", {"entity_id": cover_entity_id}, True),
        ("lock", "unlock", {"code": "1234", "entity_id": lock_entity_id}, True),
        ("lock", "lock", {"entity_id": lock_entity_id}, True),
        ("lock", "open", {"entity_id": lock_entity_id}, True),
    ]

    hass.states.async_set(cover_entity_id, "opening", {"supported_features": "bad"})
    assert cover.is_closed is False
    assert cover.is_opening is True
    assert cover.is_closing is False
    assert cover.device_class is None
    assert cover.supported_features == CoverEntityFeature(0)
    hass.states.async_set(cover_entity_id, "closing")
    assert cover.is_closing is True
    hass.states.async_set(cover_entity_id, "unknown")
    assert cover.is_closed is None
    hass.states.async_remove(cover_entity_id)
    assert cover.is_closed is None
    assert cover.current_cover_position is None
    assert cover.supported_speeds is None

    for state, locked, locking, unlocking, opened, opening, jammed in (
        ("locking", True, True, False, False, False, False),
        ("unlocked", False, False, False, False, False, False),
        ("unlocking", False, False, True, False, False, False),
        ("open", False, False, False, True, False, False),
        ("opening", False, False, False, False, True, False),
        ("jammed", None, False, False, False, False, True),
        ("unknown", None, None, None, None, None, None),
    ):
        hass.states.async_set(lock_entity_id, state)
        assert (
            lock.is_locked,
            lock.is_locking,
            lock.is_unlocking,
            lock.is_open,
            lock.is_opening,
            lock.is_jammed,
        ) == (locked, locking, unlocking, opened, opening, jammed)
    hass.states.async_remove(lock_entity_id)
    assert lock.is_locked is None
    assert lock.supported_features == LockEntityFeature(0)
    assert lock.changed_by is None
    assert lock.code_format is None
    hass.states.async_set(
        lock_entity_id, "locked", {"supported_features": "invalid", "changed_by": 7}
    )
    assert lock.supported_features == LockEntityFeature(0)
    assert lock.changed_by is None

    hass.states.async_set(
        climate_entity_id,
        "not_a_mode",
        {
            "hvac_action": "invalid",
            "hvac_modes": None,
            "temperature_unit": "invalid",
            "supported_features": "invalid",
            "current_temperature": True,
            "preset_mode": 7,
            "preset_modes": "invalid",
        },
    )
    assert climate.hvac_mode is None
    assert climate.hvac_action is None
    assert climate.hvac_modes == []
    assert climate.native_temperature_unit == hass.config.units.temperature_unit
    assert climate.supported_features == ClimateEntityFeature(0)
    assert climate.native_current_temperature is None
    assert climate.preset_mode is None
    assert climate.preset_modes is None


def test_input_and_runtime_binary_sensor_states_and_attributes(hass):
    entity_id = "binary_sensor.protection_contact"
    runtime = SimpleNamespace(
        hass=hass,
        config={
            CONF_APPLIANCE_TYPE: "sun_protection_contact",
            CONF_RUNNING_ENTITY: entity_id,
            CONF_DOOR_ENTITY: entity_id,
        },
        profile=APPLIANCE_PROFILES["sun_protection_contact"],
    )
    entry = MockConfigEntry(domain=DOMAIN, title="Blind")
    input_sensor = ApplianceInputBinarySensor(
        runtime, entry, runtime.profile.sensor_inputs[0]
    )
    input_sensor.hass = hass

    assert input_sensor.available is False
    assert input_sensor.is_on is None
    assert input_sensor.icon == "mdi:storefront-outline"
    assert input_sensor.extra_state_attributes == {"source_entity": entity_id}

    hass.states.async_set(entity_id, "unknown")
    assert input_sensor.available is True
    assert input_sensor.is_on is None
    hass.states.async_set(entity_id, "unavailable")
    assert input_sensor.available is False
    hass.states.async_set(entity_id, "off")
    assert input_sensor.available is True
    assert input_sensor.is_on is False
    assert input_sensor.icon == "mdi:storefront-outline"
    hass.states.async_set(entity_id, "on")
    assert input_sensor.is_on is True
    assert input_sensor.icon == "mdi:storefront-outline"

    running_value = [None]
    running_sensor = ApplianceBinarySensor(
        runtime, entry, "running", lambda: running_value[0]
    )
    running_sensor.hass = hass
    assert running_sensor.available is True
    assert running_sensor.is_on is None
    assert running_sensor.icon == "mdi:storefront-outline"
    assert running_sensor.extra_state_attributes == {"source_entity": entity_id}
    running_value[0] = False
    assert running_sensor.icon == "mdi:storefront-outline"
    running_value[0] = True
    assert running_sensor.icon == "mdi:storefront-outline"

    door_sensor = ApplianceBinarySensor(runtime, entry, "door", lambda: None)
    door_sensor.hass = hass
    assert door_sensor.available is True
    assert door_sensor.icon == "mdi:door"
    assert door_sensor.extra_state_attributes == {"source_entity": entity_id}
    hass.states.async_set(entity_id, "unavailable")
    assert door_sensor.available is False
    assert door_sensor.icon == "mdi:door"


@pytest.mark.parametrize(
    (
        "appliance_class",
        "appliance_type",
        "open_icon",
        "closed_icon",
        "translation_key",
    ),
    (
        ("door", "opening", "mdi:door-open", "mdi:door-closed", "door_state"),
        (
            "window",
            "opening",
            "mdi:window-open",
            "mdi:window-closed",
            "window_state",
        ),
        (
            "access",
            "access_contact",
            "mdi:garage-open",
            "mdi:garage",
            "access_state",
        ),
        (
            "awning",
            "sun_protection_contact",
            "mdi:storefront-outline",
            "mdi:storefront-outline",
            "awning_state",
        ),
    ),
)
def test_opening_contact_icons_follow_appliance_class(
    hass, appliance_class, appliance_type, open_icon, closed_icon, translation_key
):
    entity_id = "binary_sensor.opening_contact"
    hass.states.async_set(entity_id, "off")
    runtime = SimpleNamespace(
        hass=hass,
        config={
            CONF_APPLIANCE_CLASS: appliance_class,
            CONF_APPLIANCE_TYPE: appliance_type,
            CONF_RUNNING_ENTITY: entity_id,
        },
        profile=APPLIANCE_PROFILES[appliance_type],
    )
    sensor = ApplianceInputBinarySensor(
        runtime,
        MockConfigEntry(domain=DOMAIN),
        runtime.profile.sensor_inputs[0],
    )
    sensor.hass = hass

    assert sensor._attr_translation_key == translation_key
    assert sensor.icon == closed_icon
    hass.states.async_set(entity_id, "on")
    assert sensor.icon == open_icon


def test_associated_shutter_binary_sensor_has_distinct_state_translation():
    runtime = SimpleNamespace(config={CONF_APPLIANCE_TYPE: "opening"})
    sensor = ApplianceBinarySensor(
        runtime,
        MockConfigEntry(domain=DOMAIN),
        "shutter",
        lambda: False,
        BinarySensorDeviceClass.OPENING,
    )

    assert sensor._attr_translation_key == "shutter_state"


@pytest.mark.asyncio
async def test_climate_mode_transitions_run_start_and_finish_actions(
    hass, monkeypatch, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate", climate_entry.domain, "air_conditioner", config_entry=climate_entry
    )
    hass.states.async_set(climate_entity.entity_id, "off", {"hvac_action": "off"})
    config = {
        CONF_APPLIANCE_TYPE: "thermostat_climate",
        CONF_CLIMATE_ENTITY: climate_entity.entity_id,
        CONF_START_ACTIONS: [{"action": "climate.turn_on"}],
        CONF_FINISH_ACTIONS: [{"action": "climate.turn_off"}],
        "name": "Air conditioner",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    transitions: list[str] = []
    monkeypatch.setattr(
        entry.runtime_data, "_run_actions_in_background", transitions.append
    )
    hass.states.async_set(
        climate_entity.entity_id, "cool", {"hvac_action": "idle"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        climate_entity.entity_id, "off", {"hvac_action": "idle"}
    )
    await hass.async_block_till_done()

    assert transitions == [CONF_START_ACTIONS, CONF_FINISH_ACTIONS]
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.asyncio
async def test_climate_entity_with_existing_parent_is_not_reassigned(
    hass, enable_custom_integrations
):
    climate_entry = MockConfigEntry(domain="climate_source")
    climate_entry.add_to_hass(hass)
    existing_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=climate_entry.entry_id,
        identifiers={(climate_entry.domain, "existing_device")},
        name="Existing climate device",
    )
    climate_entity = er.async_get(hass).async_get_or_create(
        "climate",
        climate_entry.domain,
        "air_conditioner",
        config_entry=climate_entry,
        device_id=existing_device.id,
        original_name="Lock source name",
    )
    er.async_get(hass).async_update_entity(
        climate_entity.entity_id, name="pany porta"
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "thermostat_climate",
            CONF_CLIMATE_ENTITY: climate_entity.entity_id,
            "name": "Air conditioner",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id == (
        existing_device.id
    )
    proxy_entity_id = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"{entry.entry_id}_climate_proxy"
    )
    assert proxy_entity_id is not None
    assert er.async_get(hass).async_get(proxy_entity_id).device_id == (
        _async_appliance_device_id(hass, entry)
    )
    proxy = er.async_get(hass).async_get(proxy_entity_id)
    assert proxy.original_name == "pany porta (HAM Proxy)"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(climate_entity.entity_id).device_id == (
        existing_device.id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_domain", "entity_domain", "unique_id", "appliance_type", "source_key"),
    [
        ("cover_source", "cover", "blind", "sun_protection_cover", CONF_COVER_ENTITY),
        ("lock_source", "lock", "front_door", "opening", CONF_LOCK_ENTITY),
    ],
)
async def test_unassigned_cover_and_lock_sources_are_attached_directly(
    hass,
    enable_custom_integrations,
    source_domain,
    entity_domain,
    unique_id,
    appliance_type,
    source_key,
):
    source_config_entry = MockConfigEntry(domain=source_domain)
    source_config_entry.add_to_hass(hass)
    source_entity = er.async_get(hass).async_get_or_create(
        entity_domain,
        source_domain,
        unique_id,
        config_entry=source_config_entry,
        original_name="pany porta",
    )
    er.async_get(hass).async_update_entity(
        source_entity.entity_id, name="pany porta"
    )
    hass.states.async_set(source_entity.entity_id, "open")
    appliance_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: appliance_type,
            source_key: source_entity.entity_id,
            "name": unique_id,
        },
    )
    appliance_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(appliance_entry.entry_id)
    device_id = _async_appliance_device_id(hass, appliance_entry)
    assert device_id is not None
    attached_source = er.async_get(hass).async_get(source_entity.entity_id)
    assert attached_source.device_id == device_id
    assert attached_source.name == "pany porta"
    assert attached_source.original_name == "pany porta"
    assert (
        er.async_get(hass).async_get_entity_id(
            entity_domain,
            DOMAIN,
            f"{appliance_entry.entry_id}_{entity_domain}_proxy",
        )
        is None
    )
    assert await hass.config_entries.async_unload(appliance_entry.entry_id)
    assert er.async_get(hass).async_get(source_entity.entity_id).device_id is None


@pytest.mark.asyncio
async def test_lock_source_with_existing_parent_uses_named_visible_proxy(
    hass, enable_custom_integrations
):
    source_config_entry = MockConfigEntry(domain="lock_source")
    source_config_entry.add_to_hass(hass)
    source_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={(source_config_entry.domain, "front_door")},
        name="Physical front door",
    )
    source_entity = er.async_get(hass).async_get_or_create(
        "lock",
        source_config_entry.domain,
        "front_door",
        config_entry=source_config_entry,
        device_id=source_device.id,
        original_name="Pany porta",
    )
    hass.states.async_set(source_entity.entity_id, "locked")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_APPLIANCE_TYPE: "opening",
            CONF_LOCK_ENTITY: source_entity.entity_id,
            "name": "Porta",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    source = er.async_get(hass).async_get(source_entity.entity_id)
    assert source.device_id == source_device.id
    proxy_id = er.async_get(hass).async_get_entity_id(
        "lock", DOMAIN, f"{entry.entry_id}_lock_proxy"
    )
    assert proxy_id is not None
    assert proxy_id == (
        f"lock.porta_{source_entity.entity_id.split('.', maxsplit=1)[1]}_ham_proxy"
    )
    proxy = er.async_get(hass).async_get(proxy_id)
    assert proxy.device_id == _async_appliance_device_id(hass, entry)
    source_name = (
        source.name
        or getattr(source, "original_name_unprefixed", None)
        or source.original_name
    )
    expected_proxy_name = f"{source_name} (HAM Proxy)"
    assert proxy.original_name == expected_proxy_name
    assert proxy.hidden_by is None
    assert hass.states.get(proxy_id).attributes["friendly_name"].endswith(
        expected_proxy_name
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert er.async_get(hass).async_get(source_entity.entity_id).device_id == (
        source_device.id
    )


@pytest.mark.asyncio
async def test_unavailable_alarm_inputs_pause_without_clearing_or_false_alarm(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 2,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 3,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Refrigerator",
    }
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    door_deadline = runtime.next_door_alarm
    assert door_deadline == current_time[0] + timedelta(seconds=2)
    assert not runtime.compressor_alarm_active

    hass.states.async_set(config[CONF_DOOR_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert runtime.door_alarm_active
    assert runtime.next_door_alarm == door_deadline
    current_time[0] += timedelta(seconds=3)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == []

    hass.states.async_set(config[CONF_DOOR_ENTITY], "on")
    await hass.async_block_till_done()
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    assert not runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm is None
    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(config[CONF_POWER_ENTITY], "unavailable")
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=4)
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]
    assert runtime.next_compressor_alarm is None

    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    await _async_fire_deadline(runtime, current_time[0])
    assert actions == [CONF_DOOR_OPEN_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_refrigerator_ignores_legacy_compressor_alarm_configuration(
    hass, monkeypatch
):
    current_time = [datetime.now(timezone.utc)]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS: 60,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 0,
        "name": "Refrigerator",
    }
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    actions: list[str] = []

    async def record_action(key: str) -> None:
        actions.append(key)

    monkeypatch.setattr(runtime, "_run_actions", record_action)
    await runtime.async_setup()
    assert not runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=1)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=15)
    await _async_fire_deadline(runtime, current_time[0])
    assert runtime.detector.is_running
    assert not runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm is None

    current_time[0] += timedelta(seconds=4)
    hass.states.async_set(
        config[CONF_POWER_ENTITY], "0.5", {ATTR_UNIT_OF_MEASUREMENT: "W"}
    )
    await hass.async_block_till_done()
    current_time[0] += timedelta(seconds=60)
    await _async_fire_deadline(runtime, current_time[0])
    assert not runtime.detector.is_running
    assert not runtime.compressor_alarm_active
    assert runtime.next_compressor_alarm is None
    assert actions == [CONF_START_ACTIONS, CONF_FINISH_ACTIONS]
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_alarm_actions_do_not_overlap_on_duplicate_deadline(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.next_door_alarm = current_time
    started = asyncio.Event()
    release = asyncio.Event()
    action_calls = 0

    async def hold_action(_key: str) -> None:
        nonlocal action_calls
        action_calls += 1
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    first_action = asyncio.create_task(
        runtime._run_alarm_if_due("door", current_time)
    )
    await started.wait()
    await runtime._run_alarm_if_due("door", current_time)
    assert action_calls == 1

    release.set()
    completed_at = dt_util.utcnow()
    await first_action
    assert runtime.door_alarm_fired_count == 1
    assert runtime.next_door_alarm >= completed_at + timedelta(seconds=10)
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_old_alarm_action_does_not_overwrite_rearmed_deadline(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_DOOR_OPEN_DELAY_SECONDS: 60,
        CONF_ALARM_REPEAT_INTERVAL_SECONDS: 10,
        CONF_ALARM_REPEAT_COUNT: 1,
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.next_door_alarm = current_time
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(
        _key: str, _should_run: object | None = None
    ) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    old_action = asyncio.create_task(
        runtime._run_alarm_if_due("door", current_time)
    )
    await started.wait()

    runtime._update_alarm_condition("door", False, current_time + timedelta(seconds=1))
    runtime._update_alarm_condition("door", True, current_time + timedelta(seconds=2))
    rearmed_deadline = current_time + timedelta(seconds=62)
    release.set()
    await old_action

    assert runtime.door_alarm_fired_count == 0
    assert runtime.next_door_alarm == rearmed_deadline


@pytest.mark.asyncio
async def test_same_action_group_runs_sequentially(hass, config, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()
    active_actions = 0
    maximum_active_actions = 0

    async def hold_action(_key: str) -> None:
        nonlocal active_actions, maximum_active_actions
        active_actions += 1
        maximum_active_actions = max(maximum_active_actions, active_actions)
        if not first_started.is_set():
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
        active_actions -= 1

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    first = asyncio.create_task(runtime._run_actions_serialized(CONF_START_ACTIONS))
    await first_started.wait()
    second = asyncio.create_task(runtime._run_actions_serialized(CONF_START_ACTIONS))
    await asyncio.sleep(0)
    assert not second_started.is_set()

    release_first.set()
    await asyncio.gather(first, second)

    assert second_started.is_set()
    assert maximum_active_actions == 1


@pytest.mark.asyncio
async def test_old_pending_action_does_not_schedule_for_new_cycle(
    hass, config, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config[CONF_PENDING_ACTIONS] = [{"action": "test.pending"}]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = False
    runtime.pending_unload = True
    runtime.next_pending_reminder = current_time
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(
        _key: str, _should_run: object | None = None
    ) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    old_reminder = asyncio.create_task(runtime._async_handle_deadline(current_time))
    await started.wait()

    runtime._handle_cycle_events(
        [runtime_module.CycleEvent(runtime_module.CycleTransition.STARTED, current_time)]
    )
    release.set()
    await old_reminder

    assert runtime.pending_unload
    assert runtime.next_pending_reminder is None


@pytest.mark.asyncio
async def test_legacy_compressor_alarm_does_not_block_door_alarm(
    hass, monkeypatch
):
    current_time = datetime.now(timezone.utc)
    config = {
        CONF_APPLIANCE_TYPE: "refrigerator",
        CONF_POWER_ENTITY: "sensor.fridge_power",
        CONF_DOOR_ENTITY: "binary_sensor.fridge_door",
        CONF_DOOR_OPEN_ACTIONS: [{"action": "test.door_alarm"}],
        CONF_COMPRESSOR_INACTIVE_ACTIONS: [{"action": "test.compressor_alarm"}],
        "name": "Refrigerator",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = True
    runtime.door_alarm_active = True
    runtime.compressor_alarm_active = True
    runtime._power_available = True
    runtime.next_door_alarm = current_time
    runtime.next_compressor_alarm = current_time
    started = {
        CONF_DOOR_OPEN_ACTIONS: asyncio.Event(),
        CONF_COMPRESSOR_INACTIVE_ACTIONS: asyncio.Event(),
    }
    release = asyncio.Event()

    async def hold_action(key: str) -> None:
        started[key].set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    await runtime._async_handle_deadline(current_time)
    await asyncio.wait_for(
        started[CONF_DOOR_OPEN_ACTIONS].wait(), timeout=1
    )

    release.set()
    await hass.async_block_till_done()

    assert runtime.door_alarm_fired_count == 1
    assert runtime.compressor_alarm_fired_count == 0
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_unavailable_input_creates_and_resolves_repair_issue(
    hass, config
):
    hass.states.async_set(
        config[CONF_POWER_ENTITY],
        "unavailable",
        {ATTR_UNIT_OF_MEASUREMENT: "W"},
    )
    hass.states.async_set(config[CONF_DOOR_ENTITY], "off")
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    await runtime.async_setup()

    issue_registry = async_get_issue_registry(hass)
    issue_id = f"{entry.entry_id}_{config[CONF_POWER_ENTITY]}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(
        config[CONF_POWER_ENTITY],
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: "W"},
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    await runtime.async_unload()


@pytest.mark.asyncio
async def test_slow_pending_action_does_not_reschedule_after_unload(
    hass, config, monkeypatch
):
    config[CONF_PENDING_ACTIONS] = [{"action": "test.pending"}]
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    runtime = ApplianceRuntime(hass, entry, config)
    runtime.door_open = False
    runtime.pending_unload = True
    runtime.next_pending_reminder = datetime.now(timezone.utc)
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold_action(_key: str) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(runtime, "_run_actions", hold_action)
    await runtime._async_handle_deadline(datetime.now(timezone.utc))
    await started.wait()

    await runtime.async_unload()
    release.set()
    await hass.async_block_till_done()

    assert runtime._unsubscribe_timer is None


@pytest.mark.parametrize("appliance_type", tuple(APPLIANCE_PROFILES))
@pytest.mark.asyncio
async def test_unconfigured_optional_outputs_are_not_exposed_for_every_profile(
    hass, appliance_type, enable_custom_integrations
):
    profile = APPLIANCE_PROFILES[appliance_type]
    config = {
        CONF_APPLIANCE_TYPE: appliance_type,
        "name": f"Test {appliance_type}",
    }
    for index, input_config in enumerate(profile.sensor_inputs):
        if not input_config.required:
            continue
        source_entity_id = f"{input_config.domain}.{appliance_type}_{index}"
        config[input_config.config_key] = source_entity_id
        if input_config.domain == "sensor":
            unit = "kWh" if "energy" in input_config.device_classes else "W"
            hass.states.async_set(
                source_entity_id,
                "1",
                {ATTR_UNIT_OF_MEASUREMENT: unit},
            )
        elif input_config.domain == "climate":
            hass.states.async_set(
                source_entity_id, "off", {"hvac_action": "idle"}
            )
        else:
            hass.states.async_set(source_entity_id, "off")

    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    stale_entities = []
    for input_config in profile.sensor_inputs:
        if input_config.required:
            continue
        if (
            input_config.output_entity == "total_energy"
            and "total_energy" in profile.output_entities
            and config.get(CONF_POWER_ENTITY)
        ):
            continue
        if input_config.output_entity is not None:
            platform = input_config.domain
            unique_id = f"{entry.entry_id}_{input_config.output_entity}"
        elif input_config in profile.inputs_requiring_wrapper:
            platform = "binary_sensor"
            input_name = input_config.config_key.removesuffix("_entity")
            unique_id = f"{entry.entry_id}_input_{input_name}"
        else:
            continue
        stale_entities.append(
            registry.async_get_or_create(
                platform,
                DOMAIN,
                unique_id,
                config_entry=entry,
            )
        )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for stale_entity in stale_entities:
        assert registry.async_get(stale_entity.entity_id) is None

    input_outputs = {
        input_config.output_entity: input_config.config_key
        for input_config in profile.sensor_inputs
        if input_config.output_entity is not None
    }
    for key in ("power", "total_energy", "last_cycle_duration", "estimated_remaining"):
        config_key = input_outputs.get(key)
        if key == "total_energy":
            expected = bool(config.get(CONF_ENERGY_ENTITY)) or (
                key in profile.output_entities
                and bool(config.get(CONF_POWER_ENTITY))
            )
        else:
            expected = (
                bool(config.get(config_key))
                if config_key is not None
                else key in profile.output_entities
            )
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert (entity_id is not None) == expected

    assert await hass.config_entries.async_unload(entry.entry_id)