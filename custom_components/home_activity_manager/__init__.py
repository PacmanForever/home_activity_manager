"""Home Activity Manager integration."""

import asyncio

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .appliance_types import APPLIANCE_CATEGORIES, APPLIANCE_CATEGORY_NAMES, get_appliance_category
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
from .device import (
	register_appliance_category_devices,
	remove_legacy_profile_devices,
)
from .runtime import (
	ApplianceRuntime,
	ApplianceRuntimeCollection,
	appliance_configurations,
	entry_runtimes,
)

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


def _async_hide_proxy_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
	entity_registry = er.async_get(hass)
	proxy_unique_ids = {
		f"{entry.entry_id}_{domain}_proxy"
		for domain in ("climate", "cover", "lock")
	}
	for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
		if entity.unique_id in proxy_unique_ids and entity.hidden_by is None:
			entity_registry.async_update_entity(
				entity.entity_id,
				hidden_by=er.RegistryEntryHider.INTEGRATION,
			)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Set up all appliances owned by a category entry."""
	register_appliance_category_devices(hass, entry)
	runtimes = {}
	for appliance_id, config in appliance_configurations(entry):
		config.setdefault("_appliance_id", appliance_id)
		runtime = ApplianceRuntime(hass, entry, config)
		await runtime.async_setup()
		runtimes[appliance_id] = runtime
	entry.runtime_data = ApplianceRuntimeCollection(runtimes)
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
	remove_legacy_profile_devices(hass, entry)
	return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Unload one configured appliance."""
	if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
		return False
	for runtime in entry_runtimes(entry):
		await runtime.async_unload()
	return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
	"""Remove this appliance's integration-owned persistent state."""
	if entry.data.get("_merged_into"):
		return
	for appliance_id, _ in appliance_configurations(entry):
		store = Store(hass, 1, f"{DOMAIN}_{appliance_id}")
		await store.async_remove()


async def _async_migrate_category_entries(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Serialize category consolidation across concurrently migrating entries."""
	lock = hass.data.setdefault(f"{DOMAIN}_migration_lock", asyncio.Lock())
	async with lock:
		if entry.data.get("_merged_into") or entry not in hass.config_entries.async_entries(
			DOMAIN
		):
			return False
		return await _async_consolidate_category_entries(hass, entry)


async def _async_consolidate_category_entries(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Consolidate legacy per-appliance entries into one category entry."""
	entry_configs = appliance_configurations(entry)
	category = entry.data.get("category")
	if category not in APPLIANCE_CATEGORIES:
		category = get_appliance_category(
			entry_configs[0][1].get(CONF_APPLIANCE_TYPE) if entry_configs else None
		)
	if category not in APPLIANCE_CATEGORIES:
		hass.config_entries.async_update_entry(entry, version=8)
		return True

	matching_entries = []
	for candidate in hass.config_entries.async_entries(DOMAIN):
		candidate_configs = appliance_configurations(candidate)
		candidate_category = candidate.data.get("category")
		if candidate_category not in APPLIANCE_CATEGORIES:
			candidate_category = get_appliance_category(
				candidate_configs[0][1].get(CONF_APPLIANCE_TYPE)
				if candidate_configs
				else None
			)
		if candidate_category == category:
			matching_entries.append((candidate, candidate_configs))

	if entry not in [candidate for candidate, _ in matching_entries]:
		matching_entries.append((entry, entry_configs))

	records = []
	for candidate, candidate_configs in matching_entries:
		if isinstance(candidate.data.get("appliances"), list):
			records.extend(candidate.data["appliances"])
		else:
			records.extend(
				{
					"id": appliance_id,
					"data": dict(candidate.data),
					"options": dict(candidate.options),
				}
				for appliance_id, _ in candidate_configs
			)
		if candidate.entry_id == entry.entry_id:
			continue

		entity_registry = er.async_get(hass)
		for entity in er.async_entries_for_config_entry(
			entity_registry, candidate.entry_id
		):
			entity_registry.async_update_entity(
				entity.entity_id, config_entry_id=entry.entry_id
			)

		device_registry = dr.async_get(hass)
		for device in tuple(
			device_registry.devices.get_devices_for_config_entry_id(candidate.entry_id)
		):
			device_registry.async_update_device(
				device.id,
				add_config_entry_id=entry.entry_id,
				remove_config_entry_id=candidate.entry_id,
			)
		hass.config_entries.async_update_entry(
			candidate,
			data={"_merged_into": entry.entry_id},
			version=8,
		)
		if candidate.state is ConfigEntryState.SETUP_IN_PROGRESS:
			hass.async_create_task(
				hass.config_entries.async_remove(candidate.entry_id)
			)
		else:
			await hass.config_entries.async_remove(candidate.entry_id)

	data = {"category": category, "appliances": records}
	device_registry = dr.async_get(hass)
	category_identifier = (DOMAIN, f"category:{category}")
	for device in tuple(
		device_registry.devices.get_devices_for_config_entry_id(entry.entry_id)
	):
		if any(
			domain == DOMAIN
			and identifier.startswith("category:")
			and identifier != category_identifier[1]
			for domain, identifier in device.identifiers
		):
			device_registry.async_update_device(
				device.id, remove_config_entry_id=entry.entry_id
			)
	hass.config_entries.async_update_entry(
		entry,
		data=data,
		options={},
		title=APPLIANCE_CATEGORY_NAMES[category],
		version=8,
	)
	return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Migrate old settings and hide the integration's native-domain proxies."""
	if entry.version > 8:
		return False
	if entry.version == 8:
		return True
	if entry.version == 7:
		return await _async_migrate_category_entries(hass, entry)
	if entry.version == 6:
		_async_hide_proxy_entities(hass, entry)
		hass.config_entries.async_update_entry(entry, version=7)
		return await _async_migrate_category_entries(hass, entry)
	if entry.version == 5:
		_async_release_climate_entity(
			hass, entry, {**entry.data, **entry.options}.get(CONF_CLIMATE_ENTITY)
		)
		_async_hide_proxy_entities(hass, entry)
		hass.config_entries.async_update_entry(entry, version=7)
		return await _async_migrate_category_entries(hass, entry)

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
	if data.get(CONF_APPLIANCE_TYPE) == "air_conditioner_climate":
		data[CONF_APPLIANCE_TYPE] = "thermostat_climate"
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
	_async_hide_proxy_entities(hass, entry)
	hass.config_entries.async_update_entry(
		entry, data=data, options=options, version=7
	)
	return await _async_migrate_category_entries(hass, entry)