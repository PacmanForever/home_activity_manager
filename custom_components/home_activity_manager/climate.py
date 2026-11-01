"""Climate proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CLIMATE_ENTITY
from .entity_proxy import EntityProxyMixin
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "current_humidity",
    "current_temperature",
    "entity_picture",
    "fan_mode",
    "fan_modes",
    "friendly_name",
    "hvac_action",
    "hvac_modes",
    "icon",
    "max_humidity",
    "max_temp",
    "min_humidity",
    "min_temp",
    "preset_mode",
    "preset_modes",
    "supported_features",
    "swing_horizontal_mode",
    "swing_horizontal_modes",
    "swing_mode",
    "swing_modes",
    "target_humidity",
    "target_temp_high",
    "target_temp_low",
    "target_temp_step",
    "temperature",
    "temperature_unit",
}


class ApplianceClimateProxy(EntityProxyMixin, ClimateEntity):
    """Mirror standard climate state and forward standard climate actions."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config[CONF_CLIMATE_ENTITY],
            "climate",
            "climate_proxy",
        )
        source_state = runtime.hass.states.get(runtime.config[CONF_CLIMATE_ENTITY])
        unit = (
            source_state.attributes.get("temperature_unit")
            or source_state.attributes.get("native_temperature_unit")
            if source_state is not None
            else None
        )
        try:
            self._attr_temperature_unit = UnitOfTemperature(unit)
        except (TypeError, ValueError):
            self._attr_temperature_unit = runtime.hass.config.units.temperature_unit

    @property
    def hvac_mode(self) -> HVACMode | None:
        state = self._source_state
        if state is None:
            return None
        try:
            return HVACMode(state.state)
        except ValueError:
            return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return self._enum_values("hvac_modes", HVACMode)

    @property
    def hvac_action(self) -> HVACAction | None:
        value = self._source_attribute("hvac_action")
        if value is None:
            return None
        try:
            return HVACAction(value)
        except ValueError:
            return None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        return ClimateEntityFeature(self._supported_features_value())

    @property
    def native_temperature_unit(self) -> UnitOfTemperature:
        value = self._source_attribute("temperature_unit", "native_temperature_unit")
        try:
            return UnitOfTemperature(value)
        except (TypeError, ValueError):
            return self.hass.config.units.temperature_unit

    @property
    def native_current_temperature(self) -> float | None:
        return self._number("current_temperature", "native_current_temperature")

    @property
    def native_target_temperature(self) -> float | None:
        return self._number("temperature", "target_temperature", "native_target_temperature")

    @property
    def native_target_temperature_low(self) -> float | None:
        return self._number("target_temp_low", "native_target_temperature_low")

    @property
    def native_target_temperature_high(self) -> float | None:
        return self._number("target_temp_high", "native_target_temperature_high")

    @property
    def current_humidity(self) -> float | None:
        return self._number("current_humidity")

    @property
    def target_humidity(self) -> float | None:
        return self._number("target_humidity")

    @property
    def min_temp(self) -> float:
        return self._number("min_temp") or 7.0

    @property
    def max_temp(self) -> float:
        return self._number("max_temp") or 35.0

    @property
    def min_humidity(self) -> float:
        return self._number("min_humidity") or 30.0

    @property
    def max_humidity(self) -> float:
        return self._number("max_humidity") or 99.0

    @property
    def target_temperature_step(self) -> float | None:
        return self._number("target_temp_step", "target_temperature_step")

    @property
    def preset_mode(self) -> str | None:
        return self._string("preset_mode")

    @property
    def preset_modes(self) -> list[str] | None:
        return self._string_list("preset_modes")

    @property
    def fan_mode(self) -> str | None:
        return self._string("fan_mode")

    @property
    def fan_modes(self) -> list[str] | None:
        return self._string_list("fan_modes")

    @property
    def swing_mode(self) -> str | None:
        return self._string("swing_mode")

    @property
    def swing_modes(self) -> list[str] | None:
        return self._string_list("swing_modes")

    @property
    def swing_horizontal_mode(self) -> str | None:
        return self._string("swing_horizontal_mode")

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        return self._string_list("swing_horizontal_modes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._async_forward("climate", "set_hvac_mode", {"hvac_mode": hvac_mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        await self._async_forward("climate", "set_temperature", kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        await self._async_forward("climate", "set_humidity", {"humidity": humidity})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._async_forward("climate", "set_fan_mode", {"fan_mode": fan_mode})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._async_forward("climate", "set_preset_mode", {"preset_mode": preset_mode})

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self._async_forward("climate", "set_swing_mode", {"swing_mode": swing_mode})

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        await self._async_forward(
            "climate",
            "set_swing_horizontal_mode",
            {"swing_horizontal_mode": swing_horizontal_mode},
        )

    async def async_turn_on(self) -> None:
        await self._async_forward("climate", "turn_on")

    async def async_turn_off(self) -> None:
        await self._async_forward("climate", "turn_off")

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()

    def _supported_features_value(self) -> int:
        value = self._source_attribute("supported_features", default=0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _enum_values(self, key: str, enum_type: type) -> list[Any]:
        values = self._source_attribute(key, default=())
        output = []
        for value in values or ():
            try:
                output.append(enum_type(value))
            except ValueError:
                continue
        return output

    def _number(self, *keys: str) -> float | None:
        value = self._source_attribute(*keys)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _string(self, key: str) -> str | None:
        value = self._source_attribute(key)
        return value if isinstance(value, str) else None

    def _string_list(self, key: str) -> list[str] | None:
        value = self._source_attribute(key)
        if not isinstance(value, (list, tuple)):
            return None
        return [item for item in value if isinstance(item, str)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        if runtime.config.get(CONF_CLIMATE_ENTITY):
            async_add_entities([ApplianceClimateProxy(runtime, entry)])
            continue
        proxy_id = registry.async_get_entity_id(
            "climate", "home_activity_manager", f"{appliance_id}_climate_proxy"
        )
        if proxy_id is not None:
            registry.async_remove(proxy_id)