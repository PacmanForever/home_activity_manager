"""Sensors for Home Activity Manager."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_APPLIANCE_CLASS,
    CONF_ENERGY_ENTITY,
    CONF_ILLUMINANCE_ENTITY,
    CONF_PH_ENTITY,
    CONF_POWER_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WATER_LEVEL_ENTITY,
    DOMAIN,
)
from .appliance_types import SensorInput
from .device import appliance_device_info
from .entity_proxy import (
    _ham_proxy_name,
    _source_entity_name,
    _suggested_proxy_object_id,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes

_DURATION_TRANSLATION_KEYS = {
    "door": "door_open_duration",
    "window": "window_open_duration",
    "access": "access_open_duration",
    "awning": "awning_open_duration",
}


def _format_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total_seconds = max(0, round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class ApplianceSensor(SensorEntity):
    """A sensor backed by one runtime value."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        key: str,
        value_fn: Callable[[], Any],
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        source_entity_id: str | None = None,
    ) -> None:
        self._runtime = runtime
        self._key = key
        self._value_fn = value_fn
        self._source_entity_id = source_entity_id
        self._attr_unique_id = f"{getattr(runtime, 'appliance_id', entry.entry_id)}_{key}"
        self._attr_translation_key = (
            f"proxy_{key}" if source_entity_id else key
        )
        if source_entity_id:
            self._appliance_name = runtime.config.get("name", entry.title)
            source_name = _source_entity_name(runtime.hass, source_entity_id)
            self._attr_has_entity_name = source_name is None
            if source_name is None:
                self._appliance_name = None
            if source_name is not None:
                self._attr_name = _ham_proxy_name(source_name)
        appliance_class = runtime.config.get(CONF_APPLIANCE_CLASS)
        if key == "last_cycle_duration":
            self._attr_translation_key = _DURATION_TRANSLATION_KEYS.get(
                appliance_class, key
            )
        elif key == "shutter_last_cycle_duration":
            self._attr_translation_key = "shutter_open_duration"
        self._attr_icon = {
            "power": "mdi:flash",
            "total_energy": "mdi:lightning-bolt",
            "last_cycle_duration": "mdi:timer-check-outline",
            "shutter_last_cycle_duration": "mdi:timer-check-outline",
            "estimated_remaining": "mdi:timer-sand",
        }[key]
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    @property
    def native_value(self) -> Any:
        """Return the latest value from the appliance runtime."""
        if self._key == "power" and not self._runtime.power_available:
            return None
        return self._value_fn()

    @property
    def suggested_object_id(self) -> str:
        """Suggest a source-derived ID for source-backed sensor proxies."""
        if self._source_entity_id is None:
            return super().suggested_object_id
        return _suggested_proxy_object_id(
            self._source_entity_id, self._appliance_name
        )

    @property
    def available(self) -> bool:
        """Reflect availability of a selected source sensor."""
        source_key = None
        if self._key == "power":
            source_key = CONF_POWER_ENTITY
        elif self._key == "total_energy" and self._runtime.config.get(CONF_ENERGY_ENTITY):
            source_key = CONF_ENERGY_ENTITY
        if source_key is None:
            return super().available
        source_entity = self._runtime.config.get(source_key)
        state = self._runtime.hass.states.get(source_entity) if source_entity else None
        return state is not None and state.state != "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Identify the configured input represented by this output."""
        if self._key == "power":
            source_key = CONF_POWER_ENTITY
        elif self._key == "total_energy":
            source_key = (
                CONF_ENERGY_ENTITY
                if self._runtime.config.get(CONF_ENERGY_ENTITY)
                else CONF_POWER_ENTITY
            )
        else:
            return None
        source_entity = self._runtime.config.get(source_key)
        return {"source_entity": source_entity} if source_entity else None

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes from the shared runtime."""
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


class ApplianceInputSensor(SensorEntity):
    """Expose an optional external sensor as part of its appliance device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        input_config: SensorInput,
    ) -> None:
        self._runtime = runtime
        self._source_entity_id = runtime.config[input_config.config_key]
        self._appliance_name = runtime.config.get("name", entry.title)
        self._attr_unique_id = (
            f"{getattr(runtime, 'appliance_id', entry.entry_id)}_"
            f"{input_config.output_entity}"
        )
        self._attr_translation_key = f"proxy_{input_config.output_entity}"
        source_name = _source_entity_name(runtime.hass, self._source_entity_id)
        self._attr_has_entity_name = source_name is None
        if source_name is None:
            self._appliance_name = None
        if source_name is not None:
            self._attr_name = _ham_proxy_name(source_name)
        self._attr_icon = {
            "illuminance": "mdi:brightness-5",
            "water_temperature": "mdi:thermometer-water",
            "ph": "mdi:ph",
            "water_level": "mdi:waves-arrow-up",
        }.get(input_config.output_entity)
        source_state = runtime.hass.states.get(self._source_entity_id)
        attributes = source_state.attributes if source_state is not None else {}
        self._attr_native_unit_of_measurement = attributes.get("unit_of_measurement")
        try:
            self._attr_device_class = SensorDeviceClass(
                attributes.get("device_class")
            )
        except (TypeError, ValueError):
            self._attr_device_class = None
        try:
            self._attr_state_class = SensorStateClass(attributes.get("state_class"))
        except (TypeError, ValueError):
            self._attr_state_class = None
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    @property
    def native_value(self) -> float | str | None:
        state = self._runtime.hass.states.get(self._source_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            value = float(state.state)
        except ValueError:
            return state.state
        return value if math.isfinite(value) else None

    @property
    def suggested_object_id(self) -> str:
        """Suggest a source-derived ID for the wrapped sensor."""
        return _suggested_proxy_object_id(
            self._source_entity_id, self._appliance_name
        )

    @property
    def available(self) -> bool:
        state = self._runtime.hass.states.get(self._source_entity_id)
        return state is not None and state.state != "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"source_entity": self._source_entity_id}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up appliance sensors."""
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        proxy_sources: dict[str, str] = {}
        directly_attached_outputs: set[str] = set()
        for input_config in runtime.profile.sensor_inputs:
            if input_config.domain != "sensor" or input_config.output_entity is None:
                continue
            source_entity_id = runtime.config.get(input_config.config_key)
            if source_entity_id is None:
                continue
            if input_config.proxy_always:
                proxy_sources[input_config.output_entity] = source_entity_id
            elif use_source_entity_on_appliance(
                hass, entry, runtime, source_entity_id
            ):
                directly_attached_outputs.add(input_config.output_entity)
            else:
                proxy_sources[input_config.output_entity] = source_entity_id
        sensors = {
            "power": ApplianceSensor(
                runtime,
                entry,
                "power",
                lambda runtime=runtime: runtime.display_power_w,
                UnitOfPower.WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
                proxy_sources.get("power"),
            ),
            "total_energy": ApplianceSensor(
                runtime,
                entry,
                "total_energy",
                lambda runtime=runtime: runtime.display_energy_kwh,
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL_INCREASING,
                proxy_sources.get("total_energy"),
            ),
            "last_cycle_duration": ApplianceSensor(
                runtime,
                entry,
                "last_cycle_duration",
                lambda runtime=runtime: _format_duration(
                    runtime.detector.last_cycle_duration.total_seconds()
                    if runtime.detector.last_cycle_duration is not None
                    else None
                ),
                None,
                None,
                None,
            ),
            "shutter_last_cycle_duration": ApplianceSensor(
                runtime,
                entry,
                "shutter_last_cycle_duration",
                lambda runtime=runtime: _format_duration(
                    runtime.shutter_detector.last_cycle_duration.total_seconds()
                    if runtime.shutter_detector.last_cycle_duration is not None
                    else None
                ),
                None,
                None,
                None,
            ),
            "estimated_remaining": ApplianceSensor(
                runtime,
                entry,
                "estimated_remaining",
                lambda runtime=runtime: _format_duration(runtime.remaining_seconds),
                None,
                None,
                None,
            ),
        }
        for input_config in runtime.profile.sensor_inputs:
            key = input_config.output_entity
            if (
                input_config.domain == "sensor"
                and key is not None
                and key not in sensors
                and runtime.config.get(input_config.config_key)
                and key in proxy_sources
            ):
                sensors[key] = ApplianceInputSensor(runtime, entry, input_config)
        input_outputs = {
            input_config.output_entity: input_config.config_key
            for input_config in runtime.profile.sensor_inputs
            if input_config.output_entity is not None
        }
        expected_keys = set()
        for key in sensors:
            if key == "shutter_last_cycle_duration":
                if (
                    "shutter" in runtime.profile.output_entities
                    and (
                        runtime.config.get(CONF_SHUTTER_CONTACT_ENTITY)
                        or runtime.config.get(CONF_SHUTTER_COVER_ENTITY)
                    )
                ):
                    expected_keys.add(key)
                continue
            if key == "total_energy":
                if runtime.config.get(CONF_ENERGY_ENTITY) or (
                    key in runtime.profile.output_entities
                    and runtime.config.get(CONF_POWER_ENTITY)
                ):
                    expected_keys.add(key)
                continue
            config_key = input_outputs.get(key)
            if (
                config_key is not None
                and runtime.config.get(config_key)
                and key not in directly_attached_outputs
            ) or (
                config_key is None
                and key in runtime.profile.output_entities
            ):
                expected_keys.add(key)

        known_sensor_keys = set(sensors) | {
            input_config.output_entity
            for input_config in runtime.profile.sensor_inputs
            if input_config.domain == "sensor"
            and input_config.output_entity is not None
        }
        for key in known_sensor_keys - expected_keys:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{appliance_id}_{key}"
            )
            if entity_id is not None:
                registry.async_remove(entity_id)

        async_add_entities(
            [sensor for key, sensor in sensors.items() if key in expected_keys]
        )