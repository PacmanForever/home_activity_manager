"""Manual state-clear button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DOOR_ENTITY, CONF_ENERGY_ENTITY, CONF_POWER_ENTITY, DOMAIN
from .device import appliance_device_info
from .runtime import ApplianceRuntime, entry_runtimes


class ClearPendingButton(ButtonEntity):
    """Allow manually clearing pending-to-unload state."""

    _attr_has_entity_name = True
    _attr_translation_key = "clear_pending"
    _attr_icon = "mdi:notification-clear-all"

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._attr_unique_id = (
            f"{getattr(runtime, 'appliance_id', entry.entry_id)}_clear_pending"
        )
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    async def async_press(self) -> None:
        """Clear the pending state and cancel its reminders."""
        self._runtime.clear_pending_unload()


class ResetEnergyButton(ButtonEntity):
    """Reset the integration's displayed energy total."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_energy"
    _attr_icon = "mdi:counter"

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._attr_unique_id = (
            f"{getattr(runtime, 'appliance_id', entry.entry_id)}_energy_reset"
        )
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    async def async_press(self) -> None:
        """Reset the total without changing an external energy source."""
        self._runtime.reset_local_energy()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual-clear button when pending status is available."""
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        buttons: list[ButtonEntity] = []
        has_pending_button = (
            "clear_pending" in runtime.profile.output_entities
            and (
                runtime.config.get(CONF_DOOR_ENTITY)
                or runtime.config.get("appliance_class") == "mailbox"
                or runtime.config.get("appliance_type")
                in {"mailbox_motion", "mailbox_slot"}
            )
        )
        if has_pending_button:
            buttons.append(ClearPendingButton(runtime, entry))

        has_reset_button = bool(runtime.config.get(CONF_POWER_ENTITY)) and (
            bool(runtime.config.get(CONF_ENERGY_ENTITY))
            or "total_energy" in runtime.profile.output_entities
        )
        if has_reset_button:
            buttons.append(ResetEnergyButton(runtime, entry))

        for suffix, is_configured in (
            ("clear_pending", has_pending_button),
            ("energy_reset", has_reset_button),
        ):
            if is_configured:
                continue
            entity_id = registry.async_get_entity_id(
                "button", DOMAIN, f"{appliance_id}_{suffix}"
            )
            if entity_id is not None:
                registry.async_remove(entity_id)

        if buttons:
            async_add_entities(buttons)