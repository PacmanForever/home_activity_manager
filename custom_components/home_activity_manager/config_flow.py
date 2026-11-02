"""Configuration flows for Home Activity Manager."""

from __future__ import annotations

import math
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector
from homeassistant.helpers.storage import Store

from .appliance_types import (
    APPLIANCE_CATEGORIES,
    APPLIANCE_GROUPS,
    ApplianceTypeProfile,
    get_appliance_group_for_profile,
    get_appliance_group_name,
    get_common_group_action_groups,
    get_legacy_appliance_class,
    get_appliance_profile,
)
from .const import (
    CONF_APPLIANCE_CLASS,
    CONF_APPLIANCE_GROUP,
    CONF_APPLIANCE_TYPE,
    CONF_ALARM_REPEAT_COUNT,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_CLIMATE_ENTITY,
    CONF_COVER_ENTITY,
    CONF_COMPRESSOR_INACTIVE_ACTIONS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_DOOR_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_DOOR_OPEN_ACTIONS,
    ACTION_GROUP_CONFIG_KEYS,
    CONF_GROUP_ACTIONS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_EMPTIED_ACTIONS,
    CONF_PLUG_OFF_ACTIONS,
    CONF_PLUG_OFF_REPEAT_COUNT,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    CONF_FINISH_ACTIONS,
    CONF_FINISH_DURATION_SECONDS,
    CONF_FINISH_POWER_W,
    CONF_MAIL_ARRIVAL_ACTIONS,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_MAX_RUNTIME_ACTIONS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_ACTIONS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_PENDING_REPEATS,
    CONF_PLUG_ENTITY,
    CONF_POWER_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_START_ACTIONS,
    CONF_START_DURATION_SECONDS,
    CONF_START_POWER_W,
    DEFAULT_FINISH_DURATION_SECONDS,
    DEFAULT_FINISH_POWER_W,
    DEFAULT_ALARM_REPEAT_COUNT,
    DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS,
    DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    DEFAULT_DOOR_OPEN_DELAY_SECONDS,
    DEFAULT_PENDING_DELAY_SECONDS,
    DEFAULT_PENDING_INTERVAL_SECONDS,
    DEFAULT_PENDING_REPEATS,
    DEFAULT_PLUG_OFF_REPEAT_COUNT,
    DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
    DEFAULT_START_DURATION_SECONDS,
    DEFAULT_START_POWER_W,
    DOMAIN,
)
from .device import _get_device_by_identifier

CONF_NAME = "name"
_ENTRY_DATA_KEYS = {
    CONF_NAME,
    CONF_APPLIANCE_TYPE,
    CONF_APPLIANCE_CLASS,
    CONF_POWER_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_CLIMATE_ENTITY,
    CONF_COVER_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_RUNNING_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_PLUG_ENTITY,
    CONF_MAIL_MOTION_ENTITY,
    CONF_MAIL_SLOT_ENTITY,
}
_DURATION_CONFIG_KEYS = (
    CONF_START_DURATION_SECONDS,
    CONF_FINISH_DURATION_SECONDS,
    CONF_MAX_RUNTIME_SECONDS,
    CONF_PENDING_DELAY_SECONDS,
    CONF_PENDING_INTERVAL_SECONDS,
    CONF_DOOR_OPEN_DELAY_SECONDS,
    CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
    CONF_ALARM_REPEAT_INTERVAL_SECONDS,
    CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
)
_MAX_DURATION_SECONDS = 24 * 60 * 60


def _required(key: str, values: dict[str, Any]) -> vol.Required:
    if key in values and values[key] is not None:
        return vol.Required(key, default=values[key])
    return vol.Required(key)


def _optional(key: str, values: dict[str, Any]) -> vol.Optional:
    if key in values:
        return vol.Optional(key, default=values[key])
    return vol.Optional(key)


def _profile_step_id(step: str, profile_name: str) -> str:
    return f"{step}_{profile_name}"


class _OptionalEntitySelector(selector.EntitySelector):
    def __call__(self, data: Any) -> str | list[str] | None:
        if data is None:
            return None
        return super().__call__(data)


class _SensorSchema(vol.Schema):
    def __init__(self, schema: dict[Any, Any], optional_keys: set[str]) -> None:
        super().__init__(schema)
        self._optional_keys = optional_keys

    def __call__(self, data: Any) -> Any:
        normalized = super().__call__(data)
        if isinstance(data, dict):
            for key in self._optional_keys - data.keys():
                normalized.pop(key, None)
        return normalized


class _LockedSelectSelector(selector.SelectSelector):
    def __call__(self, data: Any) -> Any:
        return data


class _DurationSelector(selector.DurationSelector):
    def __init__(self) -> None:
        super().__init__({"enable_day": False, "allow_negative": False})

    def __call__(self, data: Any) -> Any:
        if data in (None, ""):
            return data

        if isinstance(data, (int, float)):
            return data

        if isinstance(data, str):
            parts = data.split(":")
            if (
                len(parts) == 3
                and len(parts[0]) >= 2
                and len(parts[1]) == 2
                and len(parts[2]) == 2
                and all(part.isdigit() for part in parts)
            ):
                hours, minutes, seconds = (int(part) for part in parts)
                if minutes < 60 and seconds < 60:
                    return hours * 3600 + minutes * 60 + seconds
            raise vol.Invalid("Invalid duration")

        duration = super().__call__(data)
        total_seconds = sum(
            float(duration.get(unit, 0)) * multiplier
            for unit, multiplier in (
                ("days", 86400),
                ("hours", 3600),
                ("minutes", 60),
                ("seconds", 1),
                ("milliseconds", 0.001),
            )
        )
        if not math.isfinite(total_seconds):
            raise vol.Invalid("Invalid duration")
        return round(total_seconds)


def _number_selector(unit: str, step: float = 0.1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            mode=selector.NumberSelectorMode.BOX,
            step=step,
            unit_of_measurement=unit,
        )
    )


def _duration_components_from_seconds(value: Any) -> Any:
    if value in (None, ""):
        return value
    try:
        numeric_seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)
    if not math.isfinite(numeric_seconds) or numeric_seconds < 0:
        return str(value)
    total_seconds = round(numeric_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }


def _duration_marker(
    key: str, values: dict[str, Any], default: Any = None, *, optional: bool = False
) -> vol.Marker:
    if optional:
        if key in values:
            return vol.Optional(
                key, default=_duration_components_from_seconds(values[key])
            )
        return vol.Optional(key)
    return vol.Required(
        key, default=_duration_components_from_seconds(values.get(key, default))
    )


def _identity_schema(
    values: dict[str, Any],
    appliance_groups: tuple[str, ...] = tuple(APPLIANCE_GROUPS),
) -> vol.Schema:
    return vol.Schema(
        {
            _required(CONF_NAME, values): selector.TextSelector(),
            _required(CONF_APPLIANCE_GROUP, values): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(appliance_groups),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="appliance_group",
                )
            ),
        }
    )


def _appliance_class_schema(
    group: str, values: dict[str, Any] | None = None
) -> vol.Schema:
    values = values or {}
    return vol.Schema(
        {
            _required(CONF_APPLIANCE_CLASS, values): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(APPLIANCE_GROUPS[group]),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="appliance_class",
                )
            )
        }
    )


def _activity_mode_schema(group: str, appliance_class: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("activity_mode"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(APPLIANCE_GROUPS[group][appliance_class]),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=f"activity_mode_{group}",
                )
            )
        }
    )


def _options_identity_schema(values: dict[str, Any], group: str) -> vol.Schema:
    appliance_class = values.get(CONF_APPLIANCE_CLASS) or get_legacy_appliance_class(
        values[CONF_APPLIANCE_TYPE]
    )
    assert appliance_class is not None
    _, mode = _profile_identity(values[CONF_APPLIANCE_TYPE], appliance_class)
    return vol.Schema(
        {
            _required(CONF_NAME, values): selector.TextSelector(),
            vol.Required(CONF_APPLIANCE_GROUP, default=group): _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=[group],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="appliance_group",
                    read_only=True,
                )
            ),
            vol.Required(CONF_APPLIANCE_CLASS, default=appliance_class): _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=[appliance_class],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="appliance_class",
                    read_only=True,
                )
            ),
            vol.Required("activity_mode", default=mode): _LockedSelectSelector(
                selector.SelectSelectorConfig(
                    options=[mode],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="activity_mode",
                    read_only=True,
                )
            ),
        }
    )


def _profile_identity(
    profile_name: str, appliance_class: str | None = None
) -> tuple[str, str]:
    if appliance_class is not None:
        for group, classes in APPLIANCE_GROUPS.items():
            modes = classes.get(appliance_class, {})
            for mode, name in modes.items():
                if name == profile_name:
                    return group, mode
    category, mode = next(
        (category, mode)
        for category, modes in APPLIANCE_CATEGORIES.items()
        for mode, name in modes.items()
        if name == profile_name
    )
    return (
        get_appliance_group_for_profile(profile_name, appliance_class) or category,
        mode,
    )


def _sensor_form_values(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> dict[str, Any]:
    form_values = dict(values)
    for sensor_input in profile.sensor_inputs:
        if sensor_input.config_key in values:
            form_values[sensor_input.form_key] = values[sensor_input.config_key]
    return form_values


def _normalize_sensor_values(
    values: dict[str, Any],
    profile: ApplianceTypeProfile,
    *,
    clear_missing_optional: bool = False,
) -> dict[str, Any]:
    normalized = dict(values)
    for sensor_input in profile.sensor_inputs:
        if sensor_input.form_key != sensor_input.config_key:
            if sensor_input.form_key in normalized:
                normalized[sensor_input.config_key] = normalized.pop(
                    sensor_input.form_key
                )
            elif (
                sensor_input.config_key not in normalized
                and clear_missing_optional
                and not sensor_input.required
            ):
                normalized[sensor_input.config_key] = None
        elif (
            sensor_input.form_key not in normalized
            and clear_missing_optional
            and not sensor_input.required
        ):
            normalized[sensor_input.config_key] = None
    return normalized


def _sensor_schema(
    values: dict[str, Any],
    profile: ApplianceTypeProfile,
    hass: HomeAssistant | None = None,
) -> vol.Schema:
    schema: dict[Any, Any] = {}
    optional_keys = set()
    for sensor_input in profile.sensor_inputs:
        marker = (
            _required(sensor_input.form_key, values)
            if sensor_input.required
            else _optional(sensor_input.form_key, values)
        )
        if not sensor_input.required:
            optional_keys.add(sensor_input.form_key)
        if sensor_input.device_classes:
            entity_filter = [
                {"domain": sensor_input.domain, "device_class": device_class}
                for device_class in sensor_input.device_classes
            ]
            selector_config = selector.EntitySelectorConfig(filter=entity_filter)
        else:
            selector_config = selector.EntitySelectorConfig(domain=sensor_input.domain)
        entity_selector = selector.EntitySelector(selector_config)
        schema[marker] = (
            entity_selector
            if sensor_input.required
            else _OptionalEntitySelector(selector_config)
        )
    return _SensorSchema(schema, optional_keys)


def _threshold_schema(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> vol.Schema:
    start_power = values.get(CONF_START_POWER_W, DEFAULT_START_POWER_W)
    start_duration = values.get(
        CONF_START_DURATION_SECONDS, DEFAULT_START_DURATION_SECONDS
    )
    finish_power = values.get(CONF_FINISH_POWER_W, DEFAULT_FINISH_POWER_W)
    finish_duration = values.get(
        CONF_FINISH_DURATION_SECONDS, DEFAULT_FINISH_DURATION_SECONDS
    )
    schema: dict[Any, Any] = {}
    if "power_cycle" in profile.parameter_groups:
        schema.update(
            {
                vol.Required(CONF_START_POWER_W, default=start_power): _number_selector("W"),
                _duration_marker(
                    CONF_START_DURATION_SECONDS, values, start_duration
                ): _DurationSelector(),
                vol.Required(CONF_FINISH_POWER_W, default=finish_power): _number_selector("W"),
                _duration_marker(
                    CONF_FINISH_DURATION_SECONDS, values, finish_duration
                ): _DurationSelector(),
            }
        )
    if "max_runtime" in profile.parameter_groups:
        schema[
            _duration_marker(
                CONF_MAX_RUNTIME_SECONDS, values, optional=True
            )
        ] = _DurationSelector()
    if "pending_unload" in profile.parameter_groups and values.get(CONF_DOOR_ENTITY):
        schema.update(
            {
                _duration_marker(
                    CONF_PENDING_DELAY_SECONDS,
                    values,
                    DEFAULT_PENDING_DELAY_SECONDS,
                ): _DurationSelector(),
                _duration_marker(
                    CONF_PENDING_INTERVAL_SECONDS,
                    values,
                    DEFAULT_PENDING_INTERVAL_SECONDS,
                ): _DurationSelector(),
                vol.Required(
                    CONF_PENDING_REPEATS,
                    default=values.get(CONF_PENDING_REPEATS, DEFAULT_PENDING_REPEATS),
                ): _number_selector("", step=1),
            }
        )
    if "door_alarm" in profile.parameter_groups:
        schema[
            _duration_marker(
                CONF_DOOR_OPEN_DELAY_SECONDS,
                values,
                DEFAULT_DOOR_OPEN_DELAY_SECONDS,
            )
        ] = _DurationSelector()
    if "compressor_alarm" in profile.parameter_groups:
        schema[
            _duration_marker(
                CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS,
                values,
                DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS,
            )
        ] = _DurationSelector()
    if "alarm_repeats" in profile.parameter_groups:
        schema[
            _duration_marker(
                CONF_ALARM_REPEAT_INTERVAL_SECONDS,
                values,
                DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS,
            )
        ] = _DurationSelector()
        schema[vol.Required(
            CONF_ALARM_REPEAT_COUNT,
            default=values.get(CONF_ALARM_REPEAT_COUNT, DEFAULT_ALARM_REPEAT_COUNT),
        )] = _number_selector("", step=1)
    if "plug_off_alarm" in profile.parameter_groups and values.get(CONF_PLUG_ENTITY):
        schema[
            _duration_marker(
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
                values,
                DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
            )
        ] = _DurationSelector()
        schema[vol.Required(
            CONF_PLUG_OFF_REPEAT_COUNT,
            default=values.get(
                CONF_PLUG_OFF_REPEAT_COUNT, DEFAULT_PLUG_OFF_REPEAT_COUNT
            ),
        )] = _number_selector("", step=1)
    return vol.Schema(schema)


def _action_schema(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> vol.Schema:
    schema: dict[Any, Any] = {}
    for group in profile.action_groups:
        if group == "plug_off_alarm" and not values.get(CONF_PLUG_ENTITY):
            continue
        if group == "pending_unload" and not values.get(CONF_DOOR_ENTITY):
            continue
        if group == "emptied" and not values.get(CONF_DOOR_ENTITY):
            continue
        key = ACTION_GROUP_CONFIG_KEYS[group]
        default = values.get(key, [])
        if (
            group == "cycle_start"
            and key not in values
            and any(source in profile.detection_sources for source in ("mail_motion", "mail_slot"))
        ):
            default = values.get(CONF_MAIL_ARRIVAL_ACTIONS, [])
        schema[vol.Optional(key, default=default)] = (
            selector.ActionSelector()
        )
    return vol.Schema(schema)


def _group_action_schema(
    appliance_group: str, values: dict[str, Any]
) -> vol.Schema:
    schema: dict[Any, Any] = {}
    for action_group in get_common_group_action_groups(appliance_group):
        key = ACTION_GROUP_CONFIG_KEYS[action_group]
        default = values.get(key, [])
        schema[vol.Optional(key, default=default)] = selector.ActionSelector()
    return vol.Schema(schema)


def _validate_thresholds(
    values: dict[str, Any], profile: ApplianceTypeProfile | None = None
) -> bool:
    if profile is not None and "power" not in profile.detection_sources:
        maximum = values.get(CONF_MAX_RUNTIME_SECONDS)
        if maximum in (None, ""):
            return True
        try:
            max_runtime = float(maximum)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(max_runtime) and max_runtime > 0

    try:
        start_power = float(values[CONF_START_POWER_W])
        finish_power = float(values[CONF_FINISH_POWER_W])
        start_duration = float(values[CONF_START_DURATION_SECONDS])
        finish_duration = float(values[CONF_FINISH_DURATION_SECONDS])
        maximum = values.get(CONF_MAX_RUNTIME_SECONDS)
        max_runtime = None if maximum in (None, "") else float(maximum)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    return (
        all(math.isfinite(value) for value in (start_power, finish_power))
        and finish_power >= 0
        and start_power > finish_power
        and all(
            math.isfinite(value) and value >= 0
            for value in (start_duration, finish_duration)
        )
        and (max_runtime is None or (math.isfinite(max_runtime) and max_runtime > 0))
    )


def _validate_duration_limits(values: dict[str, Any]) -> bool:
    for key in _DURATION_CONFIG_KEYS:
        value = values.get(key)
        if value in (None, ""):
            continue
        try:
            duration_seconds = float(value)
        except (TypeError, ValueError, OverflowError):
            return False
        if (
            not math.isfinite(duration_seconds)
            or duration_seconds < 0
            or duration_seconds > _MAX_DURATION_SECONDS
        ):
            return False
    return True


def _validate_sensor_values(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> bool:
    arrival_input = next(
        (
            item
            for item in profile.sensor_inputs
            if item.detection_source in ("mail_motion", "mail_slot")
        ),
        None,
    )
    if arrival_input is None:
        return True
    arrival_entity = values.get(arrival_input.config_key)
    door_entity = values.get(CONF_DOOR_ENTITY)
    return arrival_entity is None or door_entity is None or arrival_entity != door_entity


def _validate_climate_entity(
    hass: HomeAssistant, entity_id: str | None
) -> bool:
    if entity_id is None:
        return False
    entity_entry = er.async_get(hass).async_get(entity_id)
    return entity_entry is not None and entity_entry.domain == "climate"


def _validate_pending(values: dict[str, Any]) -> bool:
    try:
        delay = float(values[CONF_PENDING_DELAY_SECONDS])
        interval = float(values[CONF_PENDING_INTERVAL_SECONDS])
        repeats = float(values[CONF_PENDING_REPEATS])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (
        math.isfinite(delay)
        and delay > 0
        and delay.is_integer()
        and math.isfinite(interval)
        and interval > 0
        and interval.is_integer()
        and math.isfinite(repeats)
        and repeats >= 0
        and repeats.is_integer()
    )


def _validate_alarm_settings(
    values: dict[str, Any], profile: ApplianceTypeProfile | None = None
) -> bool:
    groups = (
        profile.parameter_groups
        if profile is not None
        else ("door_alarm", "compressor_alarm", "alarm_repeats")
    )
    positive_keys = []
    if "door_alarm" in groups:
        positive_keys.append(CONF_DOOR_OPEN_DELAY_SECONDS)
    if "compressor_alarm" in groups:
        positive_keys.append(CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS)
    if "alarm_repeats" in groups:
        positive_keys.append(CONF_ALARM_REPEAT_INTERVAL_SECONDS)

    try:
        positive_values = [float(values[key]) for key in positive_keys]
        repeats = (
            float(values[CONF_ALARM_REPEAT_COUNT])
            if "alarm_repeats" in groups
            else None
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

    if not all(
        math.isfinite(value) and value > 0 and value.is_integer()
        for value in positive_values
    ):
        return False
    return repeats is None or (
        math.isfinite(repeats) and repeats >= 0 and repeats.is_integer()
    )


def _validate_plug_off_alarm_settings(
    values: dict[str, Any], profile: ApplianceTypeProfile
) -> bool:
    if "plug_off_alarm" not in profile.parameter_groups or not values.get(
        CONF_PLUG_ENTITY
    ):
        return True
    try:
        interval = float(values[CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS])
        repeats = float(values[CONF_PLUG_OFF_REPEAT_COUNT])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (
        math.isfinite(interval)
        and interval > 0
        and interval.is_integer()
        and math.isfinite(repeats)
        and repeats >= 0
        and repeats.is_integer()
    )


def _clear_pending_settings(values: dict[str, Any]) -> None:
    values[CONF_PENDING_ACTIONS] = []
    values[CONF_PENDING_DELAY_SECONDS] = DEFAULT_PENDING_DELAY_SECONDS
    values[CONF_PENDING_INTERVAL_SECONDS] = DEFAULT_PENDING_INTERVAL_SECONDS
    values[CONF_PENDING_REPEATS] = DEFAULT_PENDING_REPEATS


def _entry_data(values: dict[str, Any]) -> dict[str, Any]:
    profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
    keys = _ENTRY_DATA_KEYS.copy()
    source_keys = {
        "power": CONF_POWER_ENTITY,
        "climate": CONF_CLIMATE_ENTITY,
        "running_sensor": CONF_RUNNING_ENTITY,
        "mail_motion": CONF_MAIL_MOTION_ENTITY,
        "mail_slot": CONF_MAIL_SLOT_ENTITY,
    }
    for source, key in source_keys.items():
        if source not in profile.detection_sources and not any(
            sensor_input.config_key == key for sensor_input in profile.sensor_inputs
        ):
            keys.discard(key)
    if not profile.supports_door_sensor:
        keys.discard(CONF_DOOR_ENTITY)
    if not profile.supports_smart_plug:
        keys.discard(CONF_PLUG_ENTITY)
    return {key: values[key] for key in keys if key in values}


def _entry_options(values: dict[str, Any]) -> dict[str, Any]:
    profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
    unsupported = set(_ENTRY_DATA_KEYS)
    if "power" not in profile.detection_sources:
        unsupported.update(
            {
                CONF_START_POWER_W,
                CONF_START_DURATION_SECONDS,
                CONF_FINISH_POWER_W,
                CONF_FINISH_DURATION_SECONDS,
            }
        )
    if "max_runtime" not in profile.parameter_groups:
        unsupported.update({CONF_MAX_RUNTIME_SECONDS, CONF_MAX_RUNTIME_ACTIONS})
    if "cycle_start" not in profile.action_groups:
        unsupported.add(CONF_START_ACTIONS)
    if "cycle_finish" not in profile.action_groups:
        unsupported.add(CONF_FINISH_ACTIONS)
    if "emptied" not in profile.action_groups or not values.get(CONF_DOOR_ENTITY):
        unsupported.add(CONF_EMPTIED_ACTIONS)
    if "mail_arrival" not in profile.action_groups:
        unsupported.add(CONF_MAIL_ARRIVAL_ACTIONS)
    if "door_open_alarm" not in profile.action_groups:
        unsupported.update({CONF_DOOR_OPEN_ACTIONS, CONF_DOOR_OPEN_DELAY_SECONDS})
    if "compressor_inactive_alarm" not in profile.action_groups:
        unsupported.update(
            {CONF_COMPRESSOR_INACTIVE_ACTIONS, CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS}
        )
    if not any(
        group in profile.action_groups
        for group in ("door_open_alarm", "compressor_inactive_alarm")
    ):
        unsupported.update({CONF_ALARM_REPEAT_COUNT, CONF_ALARM_REPEAT_INTERVAL_SECONDS})
    if "plug_off_alarm" not in profile.action_groups or not values.get(
        CONF_PLUG_ENTITY
    ):
        unsupported.update(
            {
                CONF_PLUG_OFF_ACTIONS,
                CONF_PLUG_OFF_REPEAT_COUNT,
                CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS,
            }
        )
    if "pending_unload" not in profile.parameter_groups or not values.get(
        CONF_DOOR_ENTITY
    ):
        unsupported.update(
            {
                CONF_PENDING_ACTIONS,
                CONF_PENDING_DELAY_SECONDS,
                CONF_PENDING_INTERVAL_SECONDS,
                CONF_PENDING_REPEATS,
            }
        )
    return {key: value for key, value in values.items() if key not in unsupported}


class ApplianceCycleMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup of an appliance category."""

    VERSION = 9

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}
        self._category: str | None = None
        self._existing_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            self._draft = dict(user_input)
            self._category = self._draft.pop(CONF_APPLIANCE_GROUP)
            if self.hass is not None:
                self._existing_entry = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(DOMAIN)
                        if entry.data.get("category") == self._category
                    ),
                    None,
                )
                if self._existing_entry is None:
                    await self.async_set_unique_id(self._category)
                    self._abort_if_unique_id_configured()
            return await self.async_step_appliance_class()
        return self.async_show_form(
            step_id="user",
            data_schema=_identity_schema({}),
            last_step=False,
        )

    async def async_step_appliance_class(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self._category is not None
        classes = APPLIANCE_GROUPS[self._category]
        if len(classes) == 1:
            self._draft[CONF_APPLIANCE_CLASS] = next(iter(classes))
            return await self.async_step_activity_mode()
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_activity_mode()
        return self.async_show_form(
            step_id="appliance_class",
            data_schema=_appliance_class_schema(self._category, self._draft),
            last_step=False,
        )

    async def async_step_activity_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self._category is not None
        appliance_class = self._draft[CONF_APPLIANCE_CLASS]
        if user_input is not None:
            self._draft[CONF_APPLIANCE_TYPE] = APPLIANCE_GROUPS[self._category][
                appliance_class
            ][user_input["activity_mode"]]
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id=f"activity_mode_{self._category}",
            data_schema=_activity_mode_schema(self._category, appliance_class),
            last_step=False,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            self._draft.update(_normalize_sensor_values(user_input, profile))
            if not _validate_sensor_values(self._draft, profile):
                return self.async_show_form(
                    step_id=_profile_step_id(
                        "sensors", self._draft[CONF_APPLIANCE_TYPE]
                    ),
                    data_schema=_sensor_schema(
                        _sensor_form_values(self._draft, profile), profile, self.hass
                    ),
                    errors={"base": "mailbox_sensors_must_be_distinct"},
                    last_step=False,
                )
            if "climate" in profile.detection_sources and not _validate_climate_entity(
                self.hass, self._draft.get(CONF_CLIMATE_ENTITY)
            ):
                return self.async_show_form(
                    step_id=_profile_step_id(
                        "sensors", self._draft[CONF_APPLIANCE_TYPE]
                    ),
                    data_schema=_sensor_schema(
                        _sensor_form_values(self._draft, profile), profile, self.hass
                    ),
                    errors={"base": "climate_entity_requires_no_device"},
                    last_step=False,
                )
            return await self.async_step_parameters()
        profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
        return self.async_show_form(
            step_id=_profile_step_id("sensors", self._draft[CONF_APPLIANCE_TYPE]),
            data_schema=_sensor_schema(
                _sensor_form_values(self._draft, profile), profile, self.hass
            ),
            last_step=False,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
        data_schema = _threshold_schema(self._draft, profile)
        if user_input is None and not data_schema.schema:
            return await self.async_step_actions()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_duration_limits(user_input):
                errors["base"] = "invalid_thresholds"
            elif not _validate_thresholds(user_input, profile):
                errors["base"] = "invalid_thresholds"
            elif (
                "pending_unload" in profile.parameter_groups
                and self._draft.get(CONF_DOOR_ENTITY)
                and not _validate_pending(user_input)
            ):
                errors["base"] = "invalid_pending_settings"
            elif (
                "alarm_repeats" in profile.parameter_groups
                and not _validate_alarm_settings(user_input, profile)
            ):
                errors["base"] = "invalid_alarm_settings"
            elif not _validate_plug_off_alarm_settings(
                {**self._draft, **user_input}, profile
            ):
                errors["base"] = "invalid_plug_off_alarm_settings"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id=_profile_step_id("parameters", self._draft[CONF_APPLIANCE_TYPE]),
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            self._draft.update(user_input)
            profile = get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            if "pending_unload" not in profile.parameter_groups or not self._draft.get(
                CONF_DOOR_ENTITY
            ):
                _clear_pending_settings(self._draft)
            category = self._category
            assert category is not None
            language = self.hass.config.language if self.hass is not None else "en"
            appliance = {
                "id": uuid4().hex,
                "data": _entry_data(self._draft),
                "options": _entry_options(self._draft),
            }
            if self._existing_entry is not None:
                entry = self.hass.config_entries.async_get_entry(
                    self._existing_entry.entry_id
                )
                if entry is None:
                    return self.async_abort(reason="group_no_longer_configured")
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        "appliances": [*entry.data.get("appliances", []), appliance],
                    },
                )
                return self.async_abort(reason="appliance_added")
            return self.async_create_entry(
                title=get_appliance_group_name(category, language),
                data={
                    "category": category,
                    "appliances": [appliance],
                },
            )
        return self.async_show_form(
            step_id=_profile_step_id("actions", self._draft[CONF_APPLIANCE_TYPE]),
            data_schema=_action_schema(
                self._draft, get_appliance_profile(self._draft[CONF_APPLIANCE_TYPE])
            ),
        )

    async_step_activity_mode_thermostat = async_step_activity_mode
    async_step_activity_mode_dryer = async_step_activity_mode
    async_step_activity_mode_mailbox = async_step_activity_mode
    async_step_activity_mode_refrigerator = async_step_activity_mode
    async_step_activity_mode_washer = async_step_activity_mode
    async_step_activity_mode_dishwasher = async_step_activity_mode
    async_step_activity_mode_opening = async_step_activity_mode
    async_step_activity_mode_sun_protection = async_step_activity_mode
    async_step_activity_mode_climate = async_step_activity_mode
    async_step_activity_mode_laundry = async_step_activity_mode
    async_step_activity_mode_openings = async_step_activity_mode
    async_step_activity_mode_deliveries = async_step_activity_mode
    async_step_activity_mode_refrigeration = async_step_activity_mode
    async_step_sensors_thermostat_climate = async_step_sensors
    async_step_parameters_thermostat_climate = async_step_parameters
    async_step_actions_thermostat_climate = async_step_actions
    async_step_activity_mode_climate = async_step_activity_mode
    async_step_activity_mode_laundry = async_step_activity_mode
    async_step_activity_mode_openings = async_step_activity_mode
    async_step_activity_mode_deliveries = async_step_activity_mode
    async_step_activity_mode_refrigeration = async_step_activity_mode
    async_step_sensors_laundry = async_step_sensors
    async_step_parameters_laundry = async_step_parameters
    async_step_actions_laundry = async_step_actions
    async_step_sensors_air_conditioner_contact = async_step_sensors
    async_step_parameters_air_conditioner_contact = async_step_parameters
    async_step_actions_air_conditioner_contact = async_step_actions
    async_step_sensors_air_conditioner_power = async_step_sensors
    async_step_parameters_air_conditioner_power = async_step_parameters
    async_step_actions_air_conditioner_power = async_step_actions
    async_step_sensors_washer = async_step_sensors
    async_step_parameters_washer = async_step_parameters
    async_step_actions_washer = async_step_actions
    async_step_sensors_dishwasher = async_step_sensors
    async_step_parameters_dishwasher = async_step_parameters
    async_step_actions_dishwasher = async_step_actions
    async_step_sensors_dryer = async_step_sensors
    async_step_parameters_dryer = async_step_parameters
    async_step_actions_dryer = async_step_actions
    async_step_sensors_refrigerator = async_step_sensors
    async_step_parameters_refrigerator = async_step_parameters
    async_step_actions_refrigerator = async_step_actions
    async_step_sensors_refrigerator_switch = async_step_sensors
    async_step_parameters_refrigerator_switch = async_step_parameters
    async_step_actions_refrigerator_switch = async_step_actions
    async_step_sensors_mailbox_motion = async_step_sensors
    async_step_parameters_mailbox_motion = async_step_parameters
    async_step_actions_mailbox_motion = async_step_actions
    async_step_sensors_mailbox_slot = async_step_sensors
    async_step_parameters_mailbox_slot = async_step_parameters
    async_step_actions_mailbox_slot = async_step_actions
    async_step_sensors_opening = async_step_sensors
    async_step_parameters_opening = async_step_parameters
    async_step_actions_opening = async_step_actions
    async_step_sensors_sun_protection_contact = async_step_sensors
    async_step_parameters_sun_protection_contact = async_step_parameters
    async_step_actions_sun_protection_contact = async_step_actions
    async_step_sensors_sun_protection_cover = async_step_sensors
    async_step_parameters_sun_protection_cover = async_step_parameters
    async_step_actions_sun_protection_cover = async_step_actions
    async_step_sensors_laundry = async_step_sensors
    async_step_parameters_laundry = async_step_parameters
    async_step_actions_laundry = async_step_actions

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ApplianceCycleMonitorOptionsFlow()


class ApplianceCycleMonitorOptionsFlow(OptionsFlow):
    """Handle appliance edits and additions within a category entry."""

    def __init__(self) -> None:
        self._draft: dict[str, Any] = {}
        self._saved: dict[str, Any] = {}
        self._appliance_id: str | None = None
        self._appliance_action: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        records = self.config_entry.data.get("appliances")
        if isinstance(records, list):
            if user_input is not None:
                self._appliance_action = user_input["appliance_action"]
                if self._appliance_action == "group_actions":
                    return await self.async_step_group_actions()
                return await self.async_step_select_appliance()

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("appliance_action"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["edit", "remove", "group_actions"],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                                translation_key="appliance_action",
                            )
                        )
                    }
                ),
                last_step=False,
            )

        if not self._saved:
            self._saved = {**self.config_entry.data, **self.config_entry.options}
            self._saved.setdefault(CONF_NAME, self.config_entry.title)
            self._saved.setdefault(
                CONF_APPLIANCE_CLASS,
                get_legacy_appliance_class(self._saved[CONF_APPLIANCE_TYPE]),
            )
        if user_input is not None:
            category, mode = _profile_identity(
                self._saved[CONF_APPLIANCE_TYPE], self._saved[CONF_APPLIANCE_CLASS]
            )
            if (
                user_input.get(CONF_APPLIANCE_GROUP, category) != category
                or user_input.get(
                    CONF_APPLIANCE_CLASS, self._saved[CONF_APPLIANCE_CLASS]
                )
                != self._saved[CONF_APPLIANCE_CLASS]
                or user_input.get("activity_mode", mode) != mode
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=_options_identity_schema(
                        self._saved,
                        self.config_entry.data.get("category", category),
                    ),
                    errors={"base": "appliance_type_immutable"},
                    last_step=False,
                )
            self._draft = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_APPLIANCE_TYPE: self._saved[CONF_APPLIANCE_TYPE],
                CONF_APPLIANCE_CLASS: self._saved[CONF_APPLIANCE_CLASS],
            }
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="init",
            data_schema=_options_identity_schema(
                self._saved,
                self.config_entry.data.get(
                    "category",
                    _profile_identity(
                        self._saved[CONF_APPLIANCE_TYPE],
                        self._saved.get(CONF_APPLIANCE_CLASS),
                    )[0],
                ),
            ),
            last_step=False,
        )

    async def async_step_group_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        appliance_group = self.config_entry.data["category"]
        common_groups = get_common_group_action_groups(appliance_group)
        current_actions = self.config_entry.options.get(CONF_GROUP_ACTIONS, {})
        if not isinstance(current_actions, dict):
            current_actions = {}
        if user_input is not None:
            group_actions = {
                ACTION_GROUP_CONFIG_KEYS[action_group]: user_input.get(
                    ACTION_GROUP_CONFIG_KEYS[action_group], []
                )
                for action_group in common_groups
            }
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_GROUP_ACTIONS: group_actions,
                },
            )
        return self.async_show_form(
            step_id="group_actions",
            data_schema=_group_action_schema(appliance_group, current_actions),
        )

    @staticmethod
    def _category_appliance_schema(records: list[dict[str, Any]]) -> vol.Schema:
        options = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                continue
            name = record.get("data", {}).get(CONF_NAME, "Appliance")
            options.append({"value": record["id"], "label": name})
        return vol.Schema(
            {
                vol.Required("appliance_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    async def async_step_select_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        records = self.config_entry.data["appliances"]
        if user_input is not None:
            appliance_id = user_input["appliance_id"]
            if self._appliance_action == "remove":
                if len(records) <= 1:
                    await self.hass.config_entries.async_remove(
                        self.config_entry.entry_id
                    )
                    return self.async_abort(reason="last_appliance_removed")
                registry = er.async_get(self.hass)
                for entity in tuple(registry.entities.values()):
                    if (
                        entity.config_entry_id == self.config_entry.entry_id
                        and entity.unique_id.startswith(f"{appliance_id}_")
                    ):
                        registry.async_remove(entity.entity_id)
                device_registry = dr.async_get(self.hass)
                device = _get_device_by_identifier(
                    device_registry,
                    (DOMAIN, appliance_id),
                    self.config_entry.entry_id,
                )
                if device is not None:
                    device_registry.async_remove_device(device.id)
                await Store(self.hass, 1, f"{DOMAIN}_{appliance_id}").async_remove()
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        "appliances": [
                            record
                            for record in records
                            if record.get("id") != appliance_id
                        ],
                    },
                )
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )

            record = next(record for record in records if record.get("id") == appliance_id)
            self._appliance_id = appliance_id
            self._saved = {
                **record.get("data", {}),
                **record.get("options", {}),
            }
            self._saved.setdefault(
                CONF_NAME, record.get("data", {}).get(CONF_NAME, "")
            )
            self._saved.setdefault(
                CONF_APPLIANCE_CLASS,
                get_legacy_appliance_class(self._saved[CONF_APPLIANCE_TYPE]),
            )
            return await self.async_step_edit_appliance()
        return self.async_show_form(
            step_id="select_appliance",
            data_schema=self._category_appliance_schema(records),
        )

    async def async_step_activity_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        category = self.config_entry.data["category"]
        appliance_class = self._draft[CONF_APPLIANCE_CLASS]
        if user_input is not None:
            self._draft[CONF_APPLIANCE_TYPE] = APPLIANCE_GROUPS[category][
                appliance_class
            ][user_input["activity_mode"]]
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id=f"activity_mode_{category}",
            data_schema=_activity_mode_schema(category, appliance_class),
            last_step=False,
        )

    async def async_step_appliance_class(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        category = self.config_entry.data["category"]
        classes = APPLIANCE_GROUPS[category]
        if len(classes) == 1:
            self._draft[CONF_APPLIANCE_CLASS] = next(iter(classes))
            return await self.async_step_activity_mode()
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_activity_mode()
        return self.async_show_form(
            step_id="appliance_class",
            data_schema=_appliance_class_schema(category, self._draft),
            last_step=False,
        )

    async def async_step_edit_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if user_input is not None:
            category, mode = _profile_identity(
                self._saved[CONF_APPLIANCE_TYPE],
                self._saved[CONF_APPLIANCE_CLASS],
            )
            if (
                user_input.get(CONF_APPLIANCE_GROUP, category) != category
                or user_input.get(
                    CONF_APPLIANCE_CLASS, self._saved[CONF_APPLIANCE_CLASS]
                )
                != self._saved[CONF_APPLIANCE_CLASS]
                or user_input.get("activity_mode", mode) != mode
            ):
                return self.async_show_form(
                    step_id="edit_appliance",
                    data_schema=_options_identity_schema(
                        self._saved, self.config_entry.data["category"]
                    ),
                    errors={"base": "appliance_type_immutable"},
                    last_step=False,
                )
            self._draft = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_APPLIANCE_TYPE: self._saved[CONF_APPLIANCE_TYPE],
                CONF_APPLIANCE_CLASS: self._saved[CONF_APPLIANCE_CLASS],
            }
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="edit_appliance",
            data_schema=_options_identity_schema(
                self._saved, self.config_entry.data["category"]
            ),
            last_step=False,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        if user_input is not None:
            profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            self._draft.update(
                _normalize_sensor_values(
                    user_input, profile, clear_missing_optional=True
                )
            )
            values = {**self._saved, **self._draft}
            if not _validate_sensor_values(values, profile):
                return self.async_show_form(
                    step_id=_profile_step_id("sensors", values[CONF_APPLIANCE_TYPE]),
                    data_schema=_sensor_schema(
                        _sensor_form_values(values, profile), profile, self.hass
                    ),
                    errors={"base": "mailbox_sensors_must_be_distinct"},
                    last_step=False,
                )
            if (
                "climate" in profile.detection_sources
                and not _validate_climate_entity(
                    self.hass, values.get(CONF_CLIMATE_ENTITY)
                )
            ):
                return self.async_show_form(
                    step_id=_profile_step_id("sensors", values[CONF_APPLIANCE_TYPE]),
                    data_schema=_sensor_schema(
                        _sensor_form_values(values, profile), profile, self.hass
                    ),
                    errors={"base": "climate_entity_requires_no_device"},
                    last_step=False,
                )
            return await self.async_step_parameters()
        profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
        return self.async_show_form(
            step_id=_profile_step_id("sensors", values[CONF_APPLIANCE_TYPE]),
            data_schema=_sensor_schema(
                _sensor_form_values(values, profile), profile, self.hass
            ),
            last_step=False,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
        data_schema = _threshold_schema(values, profile)
        if user_input is None and not data_schema.schema:
            return await self.async_step_actions()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _validate_duration_limits(user_input):
                errors["base"] = "invalid_thresholds"
            elif not _validate_thresholds(user_input, profile):
                errors["base"] = "invalid_thresholds"
            elif (
                "pending_unload" in profile.parameter_groups
                and values.get(CONF_DOOR_ENTITY)
                and not _validate_pending(user_input)
            ):
                errors["base"] = "invalid_pending_settings"
            elif (
                "alarm_repeats" in profile.parameter_groups
                and not _validate_alarm_settings(user_input, profile)
            ):
                errors["base"] = "invalid_alarm_settings"
            elif not _validate_plug_off_alarm_settings(
                {**values, **user_input}, profile
            ):
                errors["base"] = "invalid_plug_off_alarm_settings"
            else:
                self._draft.update(user_input)
                return await self.async_step_actions()
        return self.async_show_form(
            step_id=_profile_step_id("parameters", values[CONF_APPLIANCE_TYPE]),
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        values = {**self._saved, **self._draft}
        if user_input is not None:
            self._draft.update(user_input)
            values = {**self._saved, **self._draft}
            profile = get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            if "pending_unload" not in profile.parameter_groups or not values.get(
                CONF_DOOR_ENTITY
            ):
                _clear_pending_settings(values)
                _clear_pending_settings(self._draft)
            if isinstance(self.config_entry.data.get("appliances"), list):
                records = list(self.config_entry.data["appliances"])
                record = {
                    "id": self._appliance_id,
                    "data": _entry_data(values),
                    "options": _entry_options(values),
                }
                records = [
                    record if item.get("id") == self._appliance_id else item
                    for item in records
                ]
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, "appliances": records},
                )
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=_entry_data(values),
                title=values[CONF_NAME],
            )
            return self.async_create_entry(
                title="",
                data={
                    **(
                        {CONF_GROUP_ACTIONS: self.config_entry.options[CONF_GROUP_ACTIONS]}
                        if CONF_GROUP_ACTIONS in self.config_entry.options
                        else {}
                    ),
                    **_entry_options(values),
                },
            )
        return self.async_show_form(
            step_id=_profile_step_id("actions", values[CONF_APPLIANCE_TYPE]),
            data_schema=_action_schema(
                values, get_appliance_profile(values[CONF_APPLIANCE_TYPE])
            ),
        )

    async_step_sensors_thermostat_climate = async_step_sensors
    async_step_parameters_thermostat_climate = async_step_parameters
    async_step_actions_thermostat_climate = async_step_actions
    async_step_activity_mode_thermostat = async_step_activity_mode
    async_step_activity_mode_dryer = async_step_activity_mode
    async_step_activity_mode_mailbox = async_step_activity_mode
    async_step_activity_mode_refrigerator = async_step_activity_mode
    async_step_activity_mode_washer = async_step_activity_mode
    async_step_activity_mode_dishwasher = async_step_activity_mode
    async_step_activity_mode_opening = async_step_activity_mode
    async_step_activity_mode_sun_protection = async_step_activity_mode
    async_step_sensors_air_conditioner_contact = async_step_sensors
    async_step_parameters_air_conditioner_contact = async_step_parameters
    async_step_actions_air_conditioner_contact = async_step_actions
    async_step_sensors_air_conditioner_power = async_step_sensors
    async_step_parameters_air_conditioner_power = async_step_parameters
    async_step_actions_air_conditioner_power = async_step_actions
    async_step_sensors_washer = async_step_sensors
    async_step_parameters_washer = async_step_parameters
    async_step_actions_washer = async_step_actions
    async_step_sensors_dishwasher = async_step_sensors
    async_step_parameters_dishwasher = async_step_parameters
    async_step_actions_dishwasher = async_step_actions
    async_step_sensors_dryer = async_step_sensors
    async_step_parameters_dryer = async_step_parameters
    async_step_actions_dryer = async_step_actions
    async_step_sensors_refrigerator = async_step_sensors
    async_step_parameters_refrigerator = async_step_parameters
    async_step_actions_refrigerator = async_step_actions
    async_step_sensors_refrigerator_switch = async_step_sensors
    async_step_parameters_refrigerator_switch = async_step_parameters
    async_step_actions_refrigerator_switch = async_step_actions
    async_step_activity_mode_climate = async_step_activity_mode
    async_step_activity_mode_laundry = async_step_activity_mode
    async_step_activity_mode_openings = async_step_activity_mode
    async_step_activity_mode_deliveries = async_step_activity_mode
    async_step_activity_mode_refrigeration = async_step_activity_mode
    async_step_sensors_laundry = async_step_sensors
    async_step_parameters_laundry = async_step_parameters
    async_step_actions_laundry = async_step_actions
    async_step_sensors_mailbox_motion = async_step_sensors
    async_step_parameters_mailbox_motion = async_step_parameters
    async_step_actions_mailbox_motion = async_step_actions
    async_step_sensors_mailbox_slot = async_step_sensors
    async_step_parameters_mailbox_slot = async_step_parameters
    async_step_actions_mailbox_slot = async_step_actions
    async_step_sensors_opening = async_step_sensors
    async_step_parameters_opening = async_step_parameters
    async_step_actions_opening = async_step_actions
    async_step_sensors_sun_protection_contact = async_step_sensors
    async_step_parameters_sun_protection_contact = async_step_parameters
    async_step_actions_sun_protection_contact = async_step_actions
    async_step_sensors_sun_protection_cover = async_step_sensors
    async_step_parameters_sun_protection_cover = async_step_parameters
    async_step_actions_sun_protection_cover = async_step_actions