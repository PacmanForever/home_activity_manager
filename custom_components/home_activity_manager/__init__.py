"""Home Activity Manager integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .appliance_types import (
	APPLIANCE_CATEGORY_NAMES,
	APPLIANCE_GROUP_NAMES,
	get_appliance_group_name,
	get_appliance_category_name,
)
from .const import DOMAIN
from .device import (
	_get_device_by_identifier,
	appliance_device_info,
	remove_appliance_group_devices,
)
from .entity_proxy import (
	release_directly_attached_entities,
)
from .runtime import (
	ApplianceRuntime,
	ApplianceRuntimeCollection,
	appliance_configurations,
	entry_runtimes,
)

PLATFORMS = [
	Platform.CLIMATE,
	Platform.FAN,
	Platform.MEDIA_PLAYER,
	Platform.VACUUM,
	Platform.COVER,
	Platform.LOCK,
	Platform.SENSOR,
	Platform.BINARY_SENSOR,
	Platform.SWITCH,
	Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	await hass.config_entries.async_reload(entry.entry_id)


def _async_localize_category_defaults(
	hass: HomeAssistant, entry: ConfigEntry
) -> None:
	category = entry.data.get("category")
	if category in APPLIANCE_GROUP_NAMES:
		english_name = APPLIANCE_GROUP_NAMES[category]
		localized_name = get_appliance_group_name(category, hass.config.language)
	elif category in APPLIANCE_CATEGORY_NAMES:
		english_name = APPLIANCE_CATEGORY_NAMES[category]
		localized_name = get_appliance_category_name(category, hass.config.language)
	else:
		return
	if localized_name == english_name:
		return

	data = dict(entry.data)
	changed = False
	records = data.get("appliances")
	if isinstance(records, list):
		localized_records = []
		for record in records:
			if not isinstance(record, dict):
				localized_records.append(record)
				continue
			config = record.get("data")
			if isinstance(config, dict) and config.get("name") == english_name:
				record = {**record, "data": {**config, "name": localized_name}}
				changed = True
			localized_records.append(record)
		if changed:
			data["appliances"] = localized_records
	elif data.get("name") == english_name:
		data["name"] = localized_name
		changed = True

	title = localized_name if entry.title == english_name else entry.title
	if changed or title != entry.title:
		hass.config_entries.async_update_entry(entry, data=data, title=title)


def _async_appliance_device_id(
	hass: HomeAssistant, entry: ConfigEntry | str
) -> str | None:
	entry_id = entry.entry_id if isinstance(entry, ConfigEntry) else entry
	registry = dr.async_get(hass)
	device = _get_device_by_identifier(registry, (DOMAIN, entry_id), entry_id)
	return device.id if device is not None else None


def _async_make_proxy_entities_visible(
	hass: HomeAssistant, entry: ConfigEntry
) -> None:
	entity_registry = er.async_get(hass)
	for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
		if (
			entity.domain in (
				"climate", "cover", "lock", "media_player", "fan", "vacuum"
			)
			and entity.unique_id.endswith(f"_{entity.domain}_proxy")
			and entity.hidden_by == er.RegistryEntryHider.INTEGRATION
		):
			entity_registry.async_update_entity(
				entity.entity_id, hidden_by=None
			)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Set up all appliances owned by a category entry."""
	_async_localize_category_defaults(hass, entry)
	remove_appliance_group_devices(hass)
	runtimes = {}
	for appliance_id, config in appliance_configurations(entry):
		config.setdefault("_appliance_id", appliance_id)
		runtime = ApplianceRuntime(hass, entry, config)
		await runtime.async_setup()
		runtimes[appliance_id] = runtime
	device_registry = dr.async_get(hass)
	for appliance in entry.data.get("appliances", []):
		area_id = appliance.get("area_id")
		appliance_id = appliance.get("id")
		if not area_id or not isinstance(appliance_id, str):
			continue
		if _get_device_by_identifier(
			device_registry, (DOMAIN, appliance_id), entry.entry_id
		) is not None:
			continue
		config = runtimes[appliance_id].config
		device = device_registry.async_get_or_create(
			config_entry_id=entry.entry_id,
			**appliance_device_info(entry, config, hass),
		)
		device_registry.async_update_device(device.id, area_id=area_id)
	entry.runtime_data = ApplianceRuntimeCollection(runtimes)
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	_async_make_proxy_entities_visible(hass, entry)
	return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Unload one configured appliance."""
	if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		return False
	for runtime in entry_runtimes(entry):
		release_directly_attached_entities(hass, runtime)
		await runtime.async_unload()
	return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	"""Remove this appliance's integration-owned persistent state."""
	for appliance_id, _ in appliance_configurations(entry):
		store = Store(hass, 1, f"{DOMAIN}_{appliance_id}")
		await store.async_remove()


async def async_migrate_entry(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Provide Home Assistant's migration hook for future format changes."""
	if entry.version in (1, 13):
		hass.config_entries.async_update_entry(entry, version=14)
		return True
	return False