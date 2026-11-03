"""Cover proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_COVER_ENTITY, CONF_SHUTTER_COVER_ENTITY, DOMAIN
from .entity_proxy import (
    EntityProxyMixin,
    remove_proxy_entity,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "current_position",
    "current_tilt_position",
    "device_class",
    "entity_picture",
    "friendly_name",
    "icon",
    "supported_features",
    "supported_speeds",
}


class ApplianceCoverProxy(EntityProxyMixin, CoverEntity):
    """Mirror standard cover state and forward supported cover actions."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config.get(CONF_COVER_ENTITY)
            or runtime.config[CONF_SHUTTER_COVER_ENTITY],
            "cover",
            "cover_proxy",
        )

    @property
    def device_class(self) -> CoverDeviceClass | None:
        value = self._source_attribute("device_class")
        try:
            return CoverDeviceClass(value) if value is not None else None
        except ValueError:
            return None

    @property
    def supported_features(self) -> CoverEntityFeature:
        value = self._source_attribute("supported_features", default=0)
        try:
            return CoverEntityFeature(int(value))
        except (TypeError, ValueError):
            return CoverEntityFeature(0)

    @property
    def is_closed(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "closed"

    @property
    def is_opening(self) -> bool | None:
        state = self._source_state
        return state is not None and state.state == "opening"

    @property
    def is_closing(self) -> bool | None:
        state = self._source_state
        return state is not None and state.state == "closing"

    @property
    def current_cover_position(self) -> int | None:
        return self._number("current_position", "current_cover_position")

    @property
    def current_cover_tilt_position(self) -> int | None:
        return self._number("current_tilt_position", "current_cover_tilt_position")

    @property
    def supported_speeds(self) -> list[str] | None:
        value = self._source_attribute("supported_speeds")
        if not isinstance(value, (list, tuple)):
            return None
        return [item for item in value if isinstance(item, str)]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "open_cover", kwargs)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "close_cover", kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "set_cover_position", kwargs)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "stop_cover", kwargs)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "open_cover_tilt", kwargs)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "close_cover_tilt", kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "set_cover_tilt_position", kwargs)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        await self._async_forward("cover", "stop_cover_tilt", kwargs)

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()

    def _number(self, *keys: str) -> int | None:
        value = self._source_attribute(*keys)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        stale_shutter_id = registry.async_get_entity_id(
            "cover", DOMAIN, f"{appliance_id}_shutter"
        )
        if stale_shutter_id is not None:
            registry.async_remove(stale_shutter_id)
        source_entity_id = runtime.config.get(
            CONF_COVER_ENTITY
        ) or runtime.config.get(CONF_SHUTTER_COVER_ENTITY)
        if source_entity_id and use_source_entity_on_appliance(
            hass, entry, runtime, source_entity_id
        ):
            remove_proxy_entity(registry, "cover", appliance_id)
            continue
        if source_entity_id:
            async_add_entities([ApplianceCoverProxy(runtime, entry)])
            continue
        remove_proxy_entity(registry, "cover", appliance_id)