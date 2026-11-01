"""Shared helpers for native-domain entity proxies."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from .appliance_types import get_appliance_model
from .const import DOMAIN
from .runtime import ApplianceRuntime


class EntityProxyMixin:
    """Share source lookup, device association, and forwarding helpers."""

    _attr_entity_registry_visible_default = False

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
        self._attr_unique_id = f"{entry.entry_id}_{domain}_proxy"
        self._attr_has_entity_name = True
        self._attr_name = None
        self._attr_should_poll = False
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=runtime.config.get("name", entry.title),
            model=get_appliance_model(runtime.config.get("appliance_type")),
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

