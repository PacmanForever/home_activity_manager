"""Fan proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    FanEntity,
    FanEntityFeature,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_FAN_ENTITY
from .entity_proxy import (
    EntityProxyMixin,
    remove_proxy_entity,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "current_direction",
    "percentage",
    "percentage_step",
    "preset_mode",
    "preset_modes",
    "speed_count",
    "supported_features",
    "oscillating",
}


class ApplianceFanProxy(EntityProxyMixin, FanEntity):
    """Mirror standard fan state and forward supported controls."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config[CONF_FAN_ENTITY],
            "fan",
            "fan_proxy",
        )

    @property
    def is_on(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "on"

    @property
    def supported_features(self) -> FanEntityFeature:
        return FanEntityFeature(self._number("supported_features") or 0)

    @property
    def percentage(self) -> int | None:
        value = self._number("percentage")
        return int(value) if value is not None else None

    @property
    def speed_count(self) -> int:
        value = self._number("speed_count")
        return int(value) if value is not None else 100

    @property
    def current_direction(self) -> str | None:
        return self._string("direction", "current_direction")

    @property
    def oscillating(self) -> bool | None:
        value = self._source_attribute("oscillating")
        return value if isinstance(value, bool) else None

    @property
    def preset_mode(self) -> str | None:
        return self._string("preset_mode")

    @property
    def preset_modes(self) -> list[str] | None:
        return self._string_list("preset_modes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        service_data = dict(kwargs)
        if percentage is not None:
            service_data[ATTR_PERCENTAGE] = percentage
        if preset_mode is not None:
            service_data[ATTR_PRESET_MODE] = preset_mode
        await self._async_forward("fan", "turn_on", service_data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_forward("fan", "turn_off", kwargs)

    async def async_set_percentage(self, percentage: int) -> None:
        await self._async_forward(
            "fan", SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: percentage}
        )

    async def async_increase_speed(self, percentage_step: int | None = None) -> None:
        service_data = (
            {ATTR_PERCENTAGE_STEP: percentage_step}
            if percentage_step is not None
            else None
        )
        await self._async_forward("fan", SERVICE_INCREASE_SPEED, service_data)

    async def async_decrease_speed(self, percentage_step: int | None = None) -> None:
        service_data = (
            {ATTR_PERCENTAGE_STEP: percentage_step}
            if percentage_step is not None
            else None
        )
        await self._async_forward("fan", SERVICE_DECREASE_SPEED, service_data)

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._async_forward(
            "fan", SERVICE_OSCILLATE, {ATTR_OSCILLATING: oscillating}
        )

    async def async_set_direction(self, direction: str) -> None:
        await self._async_forward(
            "fan", SERVICE_SET_DIRECTION, {ATTR_DIRECTION: direction}
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._async_forward(
            "fan", SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: preset_mode}
        )

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()

    def _number(self, key: str) -> float | None:
        value = self._source_attribute(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _string(self, key: str, *fallback_keys: str) -> str | None:
        value = self._source_attribute(key, *fallback_keys)
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
    """Add a proxy only when the source belongs to another device."""
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        source_entity_id = runtime.config.get(CONF_FAN_ENTITY)
        if source_entity_id and use_source_entity_on_appliance(
            hass, entry, runtime, source_entity_id
        ):
            remove_proxy_entity(registry, "fan", appliance_id)
            continue
        if source_entity_id:
            async_add_entities([ApplianceFanProxy(runtime, entry)])
            continue
        remove_proxy_entity(registry, "fan", appliance_id)