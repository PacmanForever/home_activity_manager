"""Home Activity Manager integration."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .appliance_types import (
	APPLIANCE_CATEGORIES,
	APPLIANCE_CATEGORY_NAMES,
	APPLIANCE_GROUPS,
	APPLIANCE_GROUP_NAMES,
	get_appliance_group_for_profile,
	get_appliance_group_name,
	get_appliance_category,
	get_appliance_category_name,
	get_canonical_appliance_type,
	get_legacy_appliance_class,
)
from .const import (
	CONF_APPLIANCE_CLASS,
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
	_get_device_by_identifier,
	move_device_to_config_entry,
	remove_appliance_group_devices,
)
from .entity_proxy import release_directly_attached_entities
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


def _async_show_proxy_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
	entity_registry = er.async_get(hass)
	for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
		if (
			entity.domain in ("climate", "cover", "lock")
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
	entry.runtime_data = ApplianceRuntimeCollection(runtimes)
	entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
	await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
	if entry.data.get("_merged_into"):
		return
	for appliance_id, _ in appliance_configurations(entry):
		store = Store(hass, 1, f"{DOMAIN}_{appliance_id}")
		await store.async_remove()


async def _async_migrate_category_entries(
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
			dr.async_entries_for_config_entry(
				device_registry, candidate.entry_id
			)
		):
			if any(
				domain == DOMAIN
				and identifier.startswith(("category:", "profile:"))
				for domain, identifier in device.identifiers
			):
				device_registry.async_remove_device(device.id)
				continue
			move_device_to_config_entry(
				device_registry, device.id, candidate.entry_id, entry.entry_id
			)
		hass.config_entries.async_update_entry(
			candidate,
			data={"_merged_into": entry.entry_id},
			version=8,
		)
		await hass.config_entries.async_remove(candidate.entry_id)

	data = {"category": category, "appliances": records}
	device_registry = dr.async_get(hass)
	category_identifier = (DOMAIN, f"category:{category}")
	for device in tuple(
		dr.async_entries_for_config_entry(device_registry, entry.entry_id)
	):
		if any(
			domain == DOMAIN
			and identifier.startswith("category:")
			and identifier != category_identifier[1]
			for domain, identifier in device.identifiers
		):
			device_registry.async_remove_device(device.id)
	hass.config_entries.async_update_entry(
		entry,
		data=data,
		options={},
		title=get_appliance_category_name(category, hass.config.language),
		version=8,
	)
	return True


def _entry_appliance_group(entry: ConfigEntry) -> str | None:
	category = entry.data.get("category")
	if category in APPLIANCE_GROUPS:
		return category
	legacy_categories = {
		"thermostat": "climate",
		"washer": "laundry",
		"dryer": "laundry",
		"dishwasher": "laundry",
		"opening": "openings",
		"mailbox": "deliveries",
		"refrigerator": "refrigeration",
	}
	if category in legacy_categories:
		return legacy_categories[category]
	configurations = appliance_configurations(entry)
	if configurations:
		config = configurations[0][1]
		return get_appliance_group_for_profile(
			config.get(CONF_APPLIANCE_TYPE), config.get(CONF_APPLIANCE_CLASS)
		)
	return None


def _migrate_appliance_record(record: dict) -> dict:
	"""Normalize one saved appliance record to the new class/profile model."""
	migrated = dict(record)
	data = dict(record.get("data", {}))
	options = dict(record.get("options", {}))
	config = {**data, **options}
	appliance_type = config.get(CONF_APPLIANCE_TYPE)
	if appliance_type is not None:
		appliance_class = config.get(CONF_APPLIANCE_CLASS) or get_legacy_appliance_class(
			appliance_type
		)
		if appliance_type == "opening_cover" and appliance_class == "door":
			appliance_class = "access"
		data[CONF_APPLIANCE_TYPE] = get_canonical_appliance_type(appliance_type)
		if appliance_class is not None:
			data[CONF_APPLIANCE_CLASS] = appliance_class
	options.pop(CONF_APPLIANCE_CLASS, None)
	migrated["data"] = data
	migrated["options"] = options
	return migrated


async def _async_migrate_appliance_groups(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Move legacy category entries into the new appliance groups."""
	group = _entry_appliance_group(entry)
	if group is None:
		hass.config_entries.async_update_entry(entry, version=11)
		return True

	matching_entries = [
		candidate
		for candidate in hass.config_entries.async_entries(DOMAIN)
		if candidate.version < 9 and _entry_appliance_group(candidate) == group
	]
	if entry not in matching_entries:
		matching_entries.append(entry)

	records = []
	for candidate in matching_entries:
		if isinstance(candidate.data.get("appliances"), list):
			records.extend(
				_migrate_appliance_record(record)
				for record in candidate.data["appliances"]
				if isinstance(record, dict)
			)
		else:
			for appliance_id, config in appliance_configurations(candidate):
				data = dict(candidate.data)
				options = dict(candidate.options)
				data.pop("category", None)
				data.pop("appliances", None)
				data[CONF_APPLIANCE_TYPE] = config.get(CONF_APPLIANCE_TYPE)
				if config.get(CONF_APPLIANCE_CLASS) is not None:
					data[CONF_APPLIANCE_CLASS] = config[CONF_APPLIANCE_CLASS]
				records.append(
					_migrate_appliance_record(
						{"id": appliance_id, "data": data, "options": options}
					)
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
			dr.async_entries_for_config_entry(
				device_registry, candidate.entry_id
			)
		):
			if any(
				domain == DOMAIN
				and identifier.startswith(("category:", "profile:"))
				for domain, identifier in device.identifiers
			):
				device_registry.async_remove_device(device.id)
				continue
			move_device_to_config_entry(
				device_registry, device.id, candidate.entry_id, entry.entry_id
			)
		hass.config_entries.async_update_entry(
			candidate, data={"_merged_into": entry.entry_id}, version=9
		)
		await hass.config_entries.async_remove(candidate.entry_id)

	data = {"category": group, "appliances": records}
	title = get_appliance_group_name(group, hass.config.language)
	hass.config_entries.async_update_entry(
		entry, data=data, options={}, title=title, version=11
	)
	return True


async def _async_migrate_access_class(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Move saved cover-detected doors into the Access class."""
	data = dict(entry.data)
	options = dict(entry.options)
	appliances = data.get("appliances")
	if isinstance(appliances, list):
		data["appliances"] = [
			_migrate_appliance_record(record)
			if isinstance(record, dict)
			else record
			for record in appliances
		]
	else:
		config = {**data, **options}
		if (
			config.get(CONF_APPLIANCE_TYPE) == "opening_cover"
			and config.get(CONF_APPLIANCE_CLASS) == "door"
		):
			data[CONF_APPLIANCE_CLASS] = "access"
			options.pop(CONF_APPLIANCE_CLASS, None)
	hass.config_entries.async_update_entry(
		entry, data=data, options=options, version=11
	)
	return True


async def _async_migrate_to_appliance_groups(
	hass: HomeAssistant, entry: ConfigEntry
) -> bool:
	"""Run legacy and current group migrations once per Home Assistant instance."""
	lock = hass.data.setdefault(f"{DOMAIN}_group_migration_lock", asyncio.Lock())
	async with lock:
		if entry.entry_id not in {
			candidate.entry_id
			for candidate in hass.config_entries.async_entries(DOMAIN)
		}:
			return True
		if entry.version == 7 and not await _async_migrate_category_entries(hass, entry):
			return False
		if entry.version == 8:
			return await _async_migrate_appliance_groups(hass, entry)
		return entry.version == 11


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
	"""Migrate old settings and show native-domain proxies."""
	if entry.version > 11:
		return False
	if entry.version == 11:
		return True
	_async_show_proxy_entities(hass, entry)
	if entry.version == 10:
		hass.config_entries.async_update_entry(entry, version=11)
		return True
	if entry.version == 9:
		return await _async_migrate_access_class(hass, entry)
	if entry.version == 8:
		return await _async_migrate_to_appliance_groups(hass, entry)
	if entry.version == 7:
		return await _async_migrate_to_appliance_groups(hass, entry)
	if entry.version == 6:
		hass.config_entries.async_update_entry(entry, version=7)
		return await _async_migrate_to_appliance_groups(hass, entry)
	if entry.version == 5:
		_async_release_climate_entity(
			hass, entry, {**entry.data, **entry.options}.get(CONF_CLIMATE_ENTITY)
		)
		hass.config_entries.async_update_entry(entry, version=7)
		return await _async_migrate_to_appliance_groups(hass, entry)

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
		data[CONF_APPLIANCE_CLASS] = "air_conditioner"
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
		entry, data=data, options=options, version=7
	)
	return await _async_migrate_to_appliance_groups(hass, entry)