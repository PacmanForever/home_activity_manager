"""Device registry helpers for appliance category groups."""

from __future__ import annotations

import inspect
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.loader import IntegrationNotLoaded, async_get_loaded_integration

from .appliance_types import get_appliance_model
from .const import CONF_APPLIANCE_CLASS, CONF_APPLIANCE_TYPE, DOMAIN


def _get_device_by_identifier(
    registry: Any, identifier: tuple[str, str], config_entry_id: str | None = None
) -> Any:
    get_by_identifier = getattr(registry, "async_get_device_by_identifier", None)
    if get_by_identifier is not None:
        return get_by_identifier(identifier, config_entry_id)
    get_devices = getattr(registry, "async_get_devices", None)
    if get_devices is not None:
        return next(
            iter(
                get_devices(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ),
            None,
        )
    devices = registry.devices
    device_entries = (
        devices.values() if hasattr(devices, "values") else devices
    )
    return next(
        (
            device
            for device in device_entries
            if identifier in device.identifiers
            and (
                config_entry_id is None
                or getattr(device, "config_entry_id", None) == config_entry_id
                or (
                    not hasattr(device, "config_entry_id")
                    and config_entry_id in device.config_entries
                )
            )
        ),
        None,
    )


def move_device_to_config_entry(
    registry: Any, device_id: str, source_entry_id: str, target_entry_id: str
) -> None:
    """Move a device using the registry API supported by this HA version."""
    update_parameters = inspect.signature(
        type(registry).async_update_device
    ).parameters
    if "new_config_entry_id" in update_parameters:
        registry.async_update_device(
            device_id, new_config_entry_id=target_entry_id
        )
    else:
        registry.async_update_device(
            device_id,
            add_config_entry_id=target_entry_id,
            remove_config_entry_id=source_entry_id,
        )


def remove_appliance_group_devices(hass: HomeAssistant) -> None:
    """Remove empty category/profile parents and detach their appliance devices."""
    registry = dr.async_get(hass)
    get_devices = getattr(registry, "async_get_devices", None)
    devices = (
        get_devices()
        if get_devices is not None
        else registry.devices.values()
    )
    update_device = getattr(registry, "async_update_device", None)
    update_parameters = (
        inspect.signature(update_device).parameters
        if update_device is not None
        else {}
    )
    for device in tuple(devices):
        if any(
            domain == DOMAIN
            and identifier.startswith(("category:", "profile:"))
            for domain, identifier in device.identifiers
        ):
            if "via_device_id" in update_parameters:
                for child in tuple(devices):
                    if child.via_device_id == device.id:
                        update_device(child.id, via_device_id=None)
            registry.async_remove_device(device.id)


def appliance_device_info(
    entry: ConfigEntry,
    config: dict[str, Any],
    hass: HomeAssistant | None = None,
) -> DeviceInfo:
    """Return device info for a standalone configured appliance."""
    appliance_type = config.get(CONF_APPLIANCE_TYPE)
    appliance_class = config.get(CONF_APPLIANCE_CLASS)
    appliance_id = config.get("_appliance_id", entry.entry_id)
    language = hass.config.language if hass is not None else "en"
    integration_version = None
    if hass is not None:
        try:
            version = async_get_loaded_integration(hass, DOMAIN).version
        except IntegrationNotLoaded:
            pass
        else:
            if version is not None:
                integration_version = str(version)
    return DeviceInfo(
        identifiers={(DOMAIN, appliance_id)},
        name=config.get("name", entry.title),
        manufacturer="@pacmanforever",
        model=get_appliance_model(appliance_type, appliance_class, language),
        sw_version=integration_version,
    )