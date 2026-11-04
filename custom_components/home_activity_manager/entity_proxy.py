"""Shared helpers for native-domain entity proxies."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .device import appliance_device_info
from .runtime import ApplianceRuntime


def _suggested_proxy_object_id(source_entity_id: str) -> str:
    """Return an object ID that identifies this source-backed proxy."""
    _, separator, object_id = source_entity_id.partition(".")
    if not separator:
        object_id = source_entity_id
    return f"{object_id}_ham_proxy"


def use_source_entity_on_appliance(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: ApplianceRuntime,
    source_entity_id: str,
) -> bool:
    """Use an unassigned source entity directly on its appliance device."""
    entity_registry = er.async_get(hass)
    source_entry = entity_registry.async_get(source_entity_id)
    if source_entry is None:
        return False

    appliance_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **appliance_device_info(entry, runtime.config, hass),
    )
    if source_entry.device_id not in (None, appliance_device.id):
        return False
    if source_entry.device_id is None:
        entity_registry.async_update_entity(
            source_entity_id, device_id=appliance_device.id
        )
    runtime._ham_directly_attached_entities[source_entity_id] = appliance_device.id
    return True


def release_directly_attached_entities(
    hass: HomeAssistant, runtime: ApplianceRuntime
) -> None:
    """Restore source entities directly attached to an appliance device."""
    entity_registry = er.async_get(hass)
    for entity_id, device_id in tuple(
        runtime._ham_directly_attached_entities.items()
    ):
        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is not None and entity_entry.device_id == device_id:
            entity_registry.async_update_entity(entity_id, device_id=None)
    runtime._ham_directly_attached_entities.clear()


def remove_proxy_entity(registry: Any, domain: str, appliance_id: str) -> None:
    """Remove a stale native-domain proxy for an appliance."""
    proxy_id = registry.async_get_entity_id(
        domain, DOMAIN, f"{appliance_id}_{domain}_proxy"
    )
    if proxy_id is not None:
        registry.async_remove(proxy_id)


class EntityProxyMixin:
    """Share source lookup, device association, and forwarding helpers."""

    _attr_entity_registry_visible_default = True

    @property
    def suggested_object_id(self) -> str:
        """Suggest an entity ID derived from the source entity."""
        return _suggested_proxy_object_id(self._source_entity_id)

    def _init_proxy(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        source_entity_id: str,
        domain: str,
        translation_key: str,
    ) -> None:
        self._runtime = runtime
        self._source_entity_id = source_entity_id
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        self._attr_unique_id = f"{appliance_id}_{domain}_proxy"
        self._attr_has_entity_name = False
        source_entry = er.async_get(runtime.hass).async_get(source_entity_id)
        source_name = (
            source_entry.name or source_entry.original_name
            if source_entry is not None
            else None
        )
        if source_name is None:
            source_state = runtime.hass.states.get(source_entity_id)
            if source_state is not None:
                source_name = source_state.attributes.get("friendly_name")
        self._attr_name = f"{source_name} (HAM Proxy)" if source_name else None
        self._attr_should_poll = False
        self._attr_translation_key = translation_key
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    @property
    def _source_state(self) -> Any:
        return self.hass.states.get(self._source_entity_id)

    def _source_attribute(self, *keys: str, default: Any = None) -> Any:
        state = self._source_state
        if state is None:
            return default
        for key in keys:
            if key in state.attributes:
                return state.attributes[key]
        return default

    def _proxy_attributes(self, excluded: set[str]) -> dict[str, Any]:
        state = self._source_state
        attributes = (
            {
                key: value
                for key, value in state.attributes.items()
                if key not in excluded
            }
            if state is not None
            else {}
        )
        return {"source_entity": self._source_entity_id, **attributes}

    @property
    def available(self) -> bool:
        state = self._source_state
        return state is not None and state.state != "unavailable"

    async def _async_forward(
        self, domain: str, service: str, service_data: dict[str, Any] | None = None
    ) -> None:
        data = dict(service_data or {})
        data["entity_id"] = self._source_entity_id
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def _subscribe_to_runtime(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()

