"""Home Activity Manager integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import (
	CONF_APPLIANCE_TYPE,
	CONF_CLIMATE_ENTITY,
	CONF_COMPRESSOR_INACTIVE_ACTIONS,
	CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
	CONF_PLUG_OFF_ACTIONS,
	CONF_PLUG_OFF_REPEAT_COUNT,
	CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
	CONF_RUNNING_ENTITY,
	DOMAIN,
)
from .runtime import ApplianceRuntime

PLATFORMS = [
	Platform.CLIMATE,
	Platform.COVER,
	Platform.LOCK,
	Platform.SENSOR,
	Platform.BINARY_SENSOR,
	Platform.SWITCH,
	Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	await hass.config_entries.async_reload(entry.entry_id)


def _async_appliance_device_id(
	hass: HomeAssistant, entry: ConfigEntry | str
) -> str | None:
	entry_id = entry.entry_id if isinstance(entry, ConfigEntry) else entry
	registry = dr.async_get(hass)
	get_by_identifier = getattr(registry, "async_get_device_by_identifier", None)
	device = (
		get_by_identifier((DOMAIN, entry_id), entry_id)
		if get_by_identifier is not None
		else registry.async_get_device(identifiers={(DOMAIN, entry_id)})
	)
	return device.id if device is not None else None


def _async_release_climate_entity(
	hass: HomeAssistant, entry: ConfigEntry, climate_entity_id: str | None
) -> None:
	if climate_entity_id is None:
		return

	device_id = _async_appliance_device_id(hass, entry)
	entity_registry = er.async_get(hass)
	entity_entry = entity_registry.async_get(climate_entity_id)
	if (
		device_id is not None
		and entity_entry is not None
		and entity_entry.device_id == device_id
	):
		entity_registry.async_update_entity(climate_entity_id, device_id=None)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Set up one configured appliance."""
	config = {**entry.data, **entry.options}
	runtime = ApplianceRuntime(hass, entry, config)
	await runtime.async_setup()
	entry.runtime_data = runtime
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Unload one configured appliance."""
	if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		return False
	runtime = entry.runtime_data
	await runtime.async_unload()
	return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	"""Remove this appliance's integration-owned persistent state."""
	store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
	await store.async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Migrate old durations and remove obsolete profile settings."""
	if entry.version > 6:
		return False
	if entry.version == 6:
		return True
	if entry.version == 5:
		_async_release_climate_entity(
			hass, entry, {**entry.data, **entry.options}.get(CONF_CLIMATE_ENTITY)
		)
		hass.config_entries.async_update_entry(entry, version=6)
		return True

	data = dict(entry.data)
	options = dict(entry.options)
	if entry.version == 1:
		for old_key, new_key in (
			("start_duration_minutes", "start_duration_seconds"),
			("finish_duration_minutes", "finish_duration_seconds"),
			("max_runtime_minutes", "max_runtime_seconds"),
		):
			if old_key in options:
				value = options.pop(old_key)
				if value not in (None, ""):
					options[new_key] = float(value) * 60
	if {**data, **options}.get(CONF_APPLIANCE_TYPE) in {
		"air_conditioner_power",
		"air_conditioner_climate",
	}:
		data.pop(CONF_RUNNING_ENTITY, None)
		options.pop(CONF_RUNNING_ENTITY, None)
	if {**data, **options}.get(CONF_APPLIANCE_TYPE) in {
		"refrigerator",
		"refrigerator_switch",
	}:
		for key in (
			CONF_COMPRESSOR_INACTIVE_ACTIONS,
			CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
			CONF_PLUG_OFF_ACTIONS,
			CONF_PLUG_OFF_REPEAT_COUNT,
			CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
		):
			options.pop(key, None)
	_async_release_climate_entity(
		hass, entry, {**data, **options}.get(CONF_CLIMATE_ENTITY)
	)
	hass.config_entries.async_update_entry(
		entry, data=data, options=options, version=6
	)
	return True