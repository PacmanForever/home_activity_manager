"""Binary sensors for Home Activity Manager."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .appliance_types import SensorInput
from .const import (
    CONF_APPLIANCE_CLASS,
    CONF_APPLIANCE_TYPE,
    CONF_DOOR_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_SHUTTER_CONTACT_ENTITY,
    CONF_SHUTTER_COVER_ENTITY,
    DOMAIN,
)
from .device import appliance_device_info
from .entity_proxy import (
    _ham_proxy_name,
    _source_entity_name,
    _suggested_proxy_object_id,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_RUNNING_ICONS = {
    "washer": ("mdi:washing-machine", "mdi:washing-machine-off"),
    "dishwasher": ("mdi:dishwasher", "mdi:dishwasher-off"),
    "dryer": ("mdi:tumble-dryer", "mdi:tumble-dryer-off"),
    "air_conditioner": ("mdi:hvac", "mdi:hvac-off"),
    "thermostat": ("mdi:hvac", "mdi:hvac-off"),
    "refrigerator": ("mdi:fridge", "mdi:fridge-off"),
    "freezer": ("mdi:fridge", "mdi:fridge-off"),
    "blind": ("mdi:blinds-open", "mdi:blinds"),
    "awning": ("mdi:storefront-outline", "mdi:storefront-outline"),
    "door": ("mdi:door-open", "mdi:door-closed"),
    "window": ("mdi:window-open", "mdi:window-closed"),
    "access": ("mdi:garage-open", "mdi:garage"),
    "thermostat_climate": ("mdi:hvac", "mdi:hvac-off"),
    "air_conditioner_contact": ("mdi:hvac", "mdi:hvac-off"),
    "air_conditioner_power": ("mdi:hvac", "mdi:hvac-off"),
    "refrigerator_switch": ("mdi:fridge", "mdi:fridge-off"),
    "sun_protection_contact": ("mdi:storefront-outline", "mdi:storefront-outline"),
    "sun_protection_cover": ("mdi:storefront-outline", "mdi:storefront-outline"),
    "opening": ("mdi:door-open", "mdi:door-closed"),
}
_STATE_TRANSLATION_KEYS = {
    "door": "door_state",
    "window": "window_state",
    "access": "access_state",
    "awning": "awning_state",
}


def _state_translation_key(appliance_class: str | None) -> str:
    return _STATE_TRANSLATION_KEYS.get(appliance_class, "state")

_DOOR_ICONS = {
    "washer": ("mdi:washing-machine-alert", "mdi:washing-machine", "mdi:washing-machine"),
    "dishwasher": ("mdi:dishwasher-alert", "mdi:dishwasher", "mdi:dishwasher"),
    "dryer": ("mdi:tumble-dryer-alert", "mdi:tumble-dryer", "mdi:tumble-dryer"),
    "refrigerator": ("mdi:fridge-alert", "mdi:fridge", "mdi:fridge-alert-outline"),
    "freezer": ("mdi:fridge-alert", "mdi:fridge", "mdi:fridge-alert-outline"),
    "refrigerator_switch": ("mdi:fridge-alert", "mdi:fridge", "mdi:fridge-alert-outline"),
    "mailbox_motion": ("mdi:mailbox-open", "mdi:mailbox", "mdi:mailbox-outline"),
    "mailbox_slot": ("mdi:mailbox-open", "mdi:mailbox", "mdi:mailbox-outline"),
}


class ApplianceBinarySensor(BinarySensorEntity):
    """A binary sensor backed by one runtime value."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        key: str,
        value_fn: Callable[[], bool | None],
        device_class: BinarySensorDeviceClass | None = None,
        source_entity_id: str | None = None,
    ) -> None:
        self._runtime = runtime
        self._key = key
        self._value_fn = value_fn
        self._source_entity_id = source_entity_id
        self._attr_unique_id = f"{getattr(runtime, 'appliance_id', entry.entry_id)}_{key}"
        self._attr_translation_key = key
        if source_entity_id:
            source_name = _source_entity_name(runtime.hass, source_entity_id)
            self._attr_has_entity_name = True
            if source_name is not None:
                self._attr_name = _ham_proxy_name(source_name)
            self._attr_translation_key = f"proxy_{key}"
        appliance_class = runtime.config.get(CONF_APPLIANCE_CLASS)
        detection_sources = getattr(
            getattr(runtime, "profile", None), "detection_sources", ()
        )
        if key == "running" and "cover" in detection_sources:
            self._attr_translation_key = _state_translation_key(appliance_class)
        elif key == "shutter":
            self._attr_translation_key = "shutter_state"
        self._attr_device_class = device_class
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )

    @property
    def is_on(self) -> bool | None:
        """Return the current runtime state."""
        return self._value_fn()

    @property
    def suggested_object_id(self) -> str:
        """Suggest a source-derived ID for source-backed binary proxies."""
        if self._source_entity_id is None:
            return super().suggested_object_id
        return _suggested_proxy_object_id(self._source_entity_id)

    @property
    def available(self) -> bool:
        """Reflect availability of the source for input-backed entities."""
        source_key = {"door": CONF_DOOR_ENTITY, "mail_slot": CONF_MAIL_SLOT_ENTITY}.get(
            self._key
        )
        if source_key is not None:
            state = self.hass.states.get(self._runtime.config.get(source_key))
            return state is not None and state.state != "unavailable"
        if self._key == "shutter":
            source_key = (
                CONF_SHUTTER_CONTACT_ENTITY
                if self._runtime.config.get(CONF_SHUTTER_CONTACT_ENTITY)
                else CONF_SHUTTER_COVER_ENTITY
            )
            state = self.hass.states.get(self._runtime.config.get(source_key))
            return state is not None and state.state != "unavailable"
        source_input = next(
            (
                item
                for item in self._runtime.profile.sensor_inputs
                if item.detection_source in ("running_sensor", "cover")
            ),
            None,
        )
        if self._key == "running" and source_input is not None:
            state = self.hass.states.get(
                self._runtime.config.get(source_input.config_key)
            )
            if source_input.detection_source == "cover":
                return state is not None and state.state not in (
                    "unknown",
                    "unavailable",
                )
            return state is not None and state.state in ("on", "off")
        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Identify the configured input represented by this output."""
        source_key = None
        if self._key == "running":
            source_input = next(
                (
                    item
                    for item in self._runtime.profile.sensor_inputs
                    if item.detection_source is not None
                ),
                None,
            )
            source_key = source_input.config_key if source_input is not None else None
        elif self._key == "door":
            source_key = CONF_DOOR_ENTITY
        elif self._key == "mail_slot":
            source_key = CONF_MAIL_SLOT_ENTITY
        elif self._key == "shutter":
            source_key = (
                CONF_SHUTTER_CONTACT_ENTITY
                if self._runtime.config.get(CONF_SHUTTER_CONTACT_ENTITY)
                else CONF_SHUTTER_COVER_ENTITY
            )
        source_entity = self._runtime.config.get(source_key) if source_key else None
        return {"source_entity": source_entity} if source_entity else None

    @property
    def icon(self) -> str:
        """Return an icon that identifies the entity and its current state."""
        appliance_type = self._runtime.config.get("appliance_type")
        appliance_class = self._runtime.config.get(CONF_APPLIANCE_CLASS, appliance_type)
        if self._key == "running":
            icons = _RUNNING_ICONS.get(appliance_class) or _RUNNING_ICONS.get(
                appliance_type
            )
            if icons is None:
                return "mdi:power-cycle"
            return icons[1] if self.is_on is False else icons[0]
        if self._key == "door":
            icons = _DOOR_ICONS.get(appliance_class) or _DOOR_ICONS.get(
                appliance_type
            )
            if icons is not None:
                if self.is_on is None:
                    return icons[2]
                return icons[0] if self.is_on else icons[1]
            if self.is_on is None:
                return "mdi:door"
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        if self._key == "mail_slot":
            if self.is_on is None:
                return "mdi:mailbox-outline"
            return "mdi:mailbox-open-up" if self.is_on else "mdi:mailbox-up"
        if self._key == "shutter":
            return "mdi:window-shutter-open" if self.is_on else "mdi:window-shutter"
        if self._key == "pending_unload":
            if appliance_type in ("mailbox_motion", "mailbox_slot"):
                return "mdi:email-alert" if self.is_on else "mdi:email-outline"
            return "mdi:bell-alert" if self.is_on else "mdi:bell-outline"
        return "mdi:checkbox-marked-circle-outline"

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes from the shared runtime."""
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self._handle_runtime_update))

    @callback
    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


class ApplianceInputBinarySensor(BinarySensorEntity):
    """Expose a configured binary input that has no equivalent output."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        runtime: ApplianceRuntime,
        entry: ConfigEntry,
        input_config: SensorInput,
    ) -> None:
        self._runtime = runtime
        self._source_entity_id = runtime.config[input_config.config_key]
        source_name = _source_entity_name(runtime.hass, self._source_entity_id)
        self._attr_has_entity_name = True
        input_name = input_config.config_key.removesuffix("_entity")
        self._input_name = input_name
        self._attr_unique_id = (
            f"{getattr(runtime, 'appliance_id', entry.entry_id)}_input_{input_name}"
        )
        if input_config.config_key == CONF_RUNNING_ENTITY:
            self._attr_translation_key = _state_translation_key(
                runtime.config.get(CONF_APPLIANCE_CLASS)
            )
        else:
            self._attr_translation_key = f"input_{input_name}"
        self._attr_device_info = appliance_device_info(
            entry, runtime.config, getattr(runtime, "hass", None)
        )
        if source_name is not None:
            self._attr_name = _ham_proxy_name(source_name)
        if input_config.device_classes:
            self._attr_device_class = BinarySensorDeviceClass(
                input_config.device_classes[0]
            )

    @property
    def suggested_object_id(self) -> str:
        """Suggest a binary sensor ID derived from the wrapped input."""
        return _suggested_proxy_object_id(self._source_entity_id)

    @property
    def is_on(self) -> bool | None:
        """Return the source's raw binary state."""
        state = self.hass.states.get(self._source_entity_id)
        if state is None or state.state not in ("on", "off"):
            return None
        return state.state == "on"

    @property
    def available(self) -> bool:
        """Return whether the source is available."""
        state = self.hass.states.get(self._source_entity_id)
        return state is not None and state.state != "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"source_entity": self._source_entity_id}

    @property
    def icon(self) -> str | None:
        """Show a state-specific icon for contact and opening inputs."""
        if self._input_name == "running":
            appliance_type = self._runtime.config.get("appliance_type")
            appliance_class = self._runtime.config.get(
                CONF_APPLIANCE_CLASS, appliance_type
            )
            icons = _RUNNING_ICONS.get(appliance_class) or _RUNNING_ICONS.get(
                appliance_type
            )
            if icons is not None:
                return icons[1] if self.is_on is False else icons[0]
            return "mdi:door-sliding-open" if self.is_on else "mdi:door-sliding"
        if self._input_name == "door":
            if self.is_on is None:
                return "mdi:door"
            return "mdi:door-open" if self.is_on else "mdi:door-closed"
        if self._input_name == "mail_slot":
            if self.is_on is None:
                return "mdi:mailbox-outline"
            return "mdi:mailbox-open-up" if self.is_on else "mdi:mailbox-up"
        return super().icon

    async def async_added_to_hass(self) -> None:
        """Subscribe to source updates through the appliance runtime."""
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
    """Set up appliance binary sensors."""
    registry = er.async_get(hass)
    entities = []
    expected_unique_ids = set()
    entity_prefixes = set()
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        entity_prefixes.add(f"{appliance_id}_")
        runtime_entities = []
        proxy_sources: dict[str, str] = {}
        directly_attached_outputs: set[str] = set()
        for input_config in runtime.profile.sensor_inputs:
            if (
                input_config.domain != "binary_sensor"
                or input_config.output_entity is None
                or not input_config.requires_source_representation
            ):
                continue
            source_entity_id = runtime.config.get(input_config.config_key)
            if source_entity_id is None:
                continue
            if use_source_entity_on_appliance(
                hass, entry, runtime, source_entity_id
            ):
                directly_attached_outputs.add(input_config.output_entity)
            else:
                proxy_sources[input_config.output_entity] = source_entity_id
        if "running" in runtime.profile.output_entities:
            running_device_class = (
                BinarySensorDeviceClass.OPENING
                if "cover" in runtime.profile.detection_sources
                else BinarySensorDeviceClass.RUNNING
            )
            runtime_entities.append(
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "running",
                    lambda runtime=runtime: runtime.detector.is_running,
                    running_device_class,
                )
            )
        if (
            "door" in runtime.profile.output_entities
            and runtime.config.get(CONF_DOOR_ENTITY)
            and "door" not in directly_attached_outputs
        ):
            runtime_entities.append(
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "door",
                    lambda runtime=runtime: runtime.door_open,
                    BinarySensorDeviceClass.DOOR,
                    proxy_sources.get("door"),
                )
            )
        if (
            "pending_unload" in runtime.profile.output_entities
            and (
                runtime.config.get(CONF_DOOR_ENTITY)
                or runtime.config.get(CONF_APPLIANCE_CLASS) == "mailbox"
                or runtime.config.get(CONF_APPLIANCE_TYPE)
                in {"mailbox_motion", "mailbox_slot"}
            )
        ):
            appliance_type = runtime.config.get("appliance_type")
            appliance_class = runtime.config.get(CONF_APPLIANCE_CLASS)
            runtime_entities.append(
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "pending_unload",
                    lambda runtime=runtime: runtime.pending_unload,
                )
            )
        if (
            "mail_slot" in runtime.profile.output_entities
            and runtime.config.get(CONF_MAIL_SLOT_ENTITY)
            and "mail_slot" not in directly_attached_outputs
        ):
            runtime_entities.append(
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "mail_slot",
                    lambda runtime=runtime: runtime.mail_slot_open,
                    BinarySensorDeviceClass.DOOR,
                    proxy_sources.get("mail_slot"),
                )
            )
        if (
            "shutter" in runtime.profile.output_entities
            and (
                runtime.config.get(CONF_SHUTTER_CONTACT_ENTITY)
                or runtime.config.get(CONF_SHUTTER_COVER_ENTITY)
            )
            and "shutter" not in directly_attached_outputs
        ):
            runtime_entities.append(
                ApplianceBinarySensor(
                    runtime,
                    entry,
                    "shutter",
                    lambda runtime=runtime: runtime.shutter_open,
                    BinarySensorDeviceClass.OPENING,
                    proxy_sources.get("shutter"),
                )
            )
        input_wrappers = tuple(
            input_config
            for input_config in runtime.profile.inputs_requiring_wrapper
            if input_config.domain == "binary_sensor"
            and runtime.config.get(input_config.config_key)
            and not use_source_entity_on_appliance(
                hass,
                entry,
                runtime,
                runtime.config[input_config.config_key],
            )
        )
        entities.extend(runtime_entities)
        expected_unique_ids.update(entity.unique_id for entity in runtime_entities)
        expected_unique_ids.update(
            f"{appliance_id}_input_{input_config.config_key.removesuffix('_entity')}"
            for input_config in input_wrappers
        )
        entities.extend(
            ApplianceInputBinarySensor(runtime, entry, input_config)
            for input_config in input_wrappers
        )

    for registered_entity in tuple(registry.entities.values()):
        if (
            registered_entity.config_entry_id == entry.entry_id
            and registered_entity.domain == "binary_sensor"
            and any(
                registered_entity.unique_id.startswith(prefix)
                for prefix in entity_prefixes
            )
            and registered_entity.unique_id not in expected_unique_ids
        ):
            registry.async_remove(registered_entity.entity_id)
    if entities:
        async_add_entities(entities)
