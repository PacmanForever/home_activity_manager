"""Vacuum proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    ATTR_COMMAND,
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    StateVacuumEntity,
)
from homeassistant.components.vacuum.const import VacuumActivity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VACUUM_ENTITY
from .entity_proxy import (
    EntityProxyMixin,
    remove_proxy_entity,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "battery_icon",
    "battery_level",
    "fan_speed",
    "fan_speed_list",
    "supported_features",
}


class ApplianceVacuumProxy(EntityProxyMixin, StateVacuumEntity):
    """Mirror vacuum activity and forward its supported controls."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config[CONF_VACUUM_ENTITY],
            "vacuum",
            "vacuum_proxy",
        )

    @property
    def activity(self) -> VacuumActivity | None:
        state = self._source_state
        if state is None:
            return None
        try:
            return VacuumActivity(state.state)
        except ValueError:
            return None

    @property
    def supported_features(self) -> VacuumEntityFeature:
        return VacuumEntityFeature(self._number("supported_features") or 0)

    @property
    def battery_level(self) -> int | None:
        value = self._number("battery_level")
        return int(value) if value is not None else None

    @property
    def fan_speed(self) -> str | None:
        return self._string("fan_speed")

    @property
    def fan_speed_list(self) -> list[str]:
        value = self._source_attribute("fan_speed_list")
        if not isinstance(value, (list, tuple)):
            return []
        return [item for item in value if isinstance(item, str)]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_start(self) -> None:
        await self._async_forward("vacuum", SERVICE_START)

    async def async_pause(self) -> None:
        await self._async_forward("vacuum", SERVICE_PAUSE)

    async def async_stop(self, **kwargs: Any) -> None:
        await self._async_forward("vacuum", SERVICE_STOP, kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self._async_forward("vacuum", SERVICE_RETURN_TO_BASE, kwargs)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        await self._async_forward("vacuum", SERVICE_CLEAN_SPOT, kwargs)

    async def async_locate(self, **kwargs: Any) -> None:
        await self._async_forward("vacuum", SERVICE_LOCATE, kwargs)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        await self._async_forward(
            "vacuum", SERVICE_SET_FAN_SPEED, {ATTR_FAN_SPEED: fan_speed, **kwargs}
        )

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        service_data = {ATTR_COMMAND: command, **kwargs}
        if params is not None:
            service_data[ATTR_PARAMS] = params
        await self._async_forward("vacuum", SERVICE_SEND_COMMAND, service_data)

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()

    def _number(self, key: str) -> float | None:
        value = self._source_attribute(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _string(self, key: str) -> str | None:
        value = self._source_attribute(key)
        return value if isinstance(value, str) else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a proxy only when the source belongs to another device."""
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        source_entity_id = runtime.config.get(CONF_VACUUM_ENTITY)
        if source_entity_id and use_source_entity_on_appliance(
            hass, entry, runtime, source_entity_id
        ):
            remove_proxy_entity(registry, "vacuum", appliance_id)
            continue
        if source_entity_id:
            async_add_entities([ApplianceVacuumProxy(runtime, entry)])
            continue
        remove_proxy_entity(registry, "vacuum", appliance_id)