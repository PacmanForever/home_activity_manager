"""Lock proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LOCK_ENTITY
from .entity_proxy import (
    EntityProxyMixin,
    remove_proxy_entity,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "changed_by",
    "code_format",
    "entity_picture",
    "friendly_name",
    "icon",
    "supported_features",
}


class ApplianceLockProxy(EntityProxyMixin, LockEntity):
    """Mirror standard lock state and forward standard lock actions."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config[CONF_LOCK_ENTITY],
            "lock",
            "lock_proxy",
        )

    @property
    def supported_features(self) -> LockEntityFeature:
        value = self._source_attribute("supported_features", default=0)
        try:
            return LockEntityFeature(int(value))
        except (TypeError, ValueError):
            return LockEntityFeature(0)

    @property
    def code_format(self) -> str | None:
        value = self._source_attribute("code_format")
        return value if isinstance(value, str) else None

    @property
    def is_locked(self) -> bool | None:
        state = self._source_state
        if state is None:
            return None
        if state.state in ("locked", "locking"):
            return True
        if state.state in ("unlocked", "unlocking", "open", "opening"):
            return False
        return None

    @property
    def is_locking(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "locking"

    @property
    def is_unlocking(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "unlocking"

    @property
    def is_open(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "open"

    @property
    def is_opening(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "opening"

    @property
    def is_jammed(self) -> bool | None:
        state = self._source_state
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state == "jammed"

    @property
    def changed_by(self) -> str | None:
        value = self._source_attribute("changed_by")
        return value if isinstance(value, str) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_lock(self, **kwargs: Any) -> None:
        await self._async_forward("lock", "lock", kwargs)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._async_forward("lock", "unlock", kwargs)

    async def async_open(self, **kwargs: Any) -> None:
        await self._async_forward("lock", "open", kwargs)

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        source_entity_id = runtime.config.get(CONF_LOCK_ENTITY)
        if source_entity_id and use_source_entity_on_appliance(
            hass, entry, runtime, source_entity_id
        ):
            remove_proxy_entity(registry, "lock", appliance_id)
            continue
        if source_entity_id:
            async_add_entities([ApplianceLockProxy(runtime, entry)])
            continue
        remove_proxy_entity(registry, "lock", appliance_id)