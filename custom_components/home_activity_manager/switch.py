"""Smart plug switch platform for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PLUG_ENTITY, DOMAIN
from .device import appliance_device_info
from .entity_proxy import _suggested_proxy_object_id
from .runtime import ApplianceRuntime, entry_runtimes


class AppliancePlugSwitch(SwitchEntity):
    """Expose control of the selected external smart plug."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "plug"

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._entity_id = runtime.config[CONF_PLUG_ENTITY]
        self._attr_unique_id = (
            f"{getattr(runtime, 'appliance_id', entry.entry_id)}_plug"
        )
        self._attr_device_info = appliance_device_info(entry, runtime.config)

    @property
    def suggested_object_id(self) -> str:
        """Suggest a switch entity ID derived from the wrapped plug."""
        return _suggested_proxy_object_id(self._entity_id)

    @property
    def is_on(self) -> bool | None:
        """Return the selected plug's current state."""
        state = self.hass.states.get(self._entity_id)
        if state is None or state.state not in ("on", "off"):
            return None
        return state.state == "on"

    @property
    def icon(self) -> str:
        """Reflect whether the selected smart plug is on or off."""
        if not self.available or self.is_on is None:
            return "mdi:power-plug-off-outline"
        return "mdi:power-plug" if self.is_on else "mdi:power-plug-off"

    @property
    def available(self) -> bool:
        """Return whether the selected plug is available."""
        state = self.hass.states.get(self._entity_id)
        return state is not None and state.state != "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"source_entity": self._entity_id}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the selected external plug."""
        await self.hass.services.async_call(
            "switch", "turn_on", {"entity_id": self._entity_id}, blocking=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the selected external plug."""
        await self.hass.services.async_call(
            "switch", "turn_off", {"entity_id": self._entity_id}, blocking=True
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime state changes."""
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
    """Set up the selected smart plug, if configured."""
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        switches = (
            [AppliancePlugSwitch(runtime, entry)]
            if runtime.config.get(CONF_PLUG_ENTITY)
            else []
        )
        if not switches:
            entity_id = registry.async_get_entity_id(
                "switch", DOMAIN, f"{appliance_id}_plug"
            )
            if entity_id is not None:
                registry.async_remove(entity_id)
        if switches:
            async_add_entities(switches)