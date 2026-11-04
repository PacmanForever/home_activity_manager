"""Constants for Home Activity Manager."""

DOMAIN = "home_activity_manager"

CONF_APPLIANCE_TYPE = "appliance_type"
CONF_APPLIANCE_GROUP = "appliance_group"
CONF_APPLIANCE_CLASS = "appliance_class"
CONF_POWER_ENTITY = "power_entity"
CONF_ENERGY_ENTITY = "energy_entity"
CONF_ILLUMINANCE_ENTITY = "illuminance_entity"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_PH_ENTITY = "ph_entity"
CONF_WATER_LEVEL_ENTITY = "water_level_entity"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_COVER_ENTITY = "cover_entity"
CONF_SHUTTER_CONTACT_ENTITY = "shutter_contact_entity"
CONF_SHUTTER_COVER_ENTITY = "shutter_cover_entity"
CONF_LOCK_ENTITY = "lock_entity"
CONF_RUNNING_ENTITY = "running_entity"
CONF_MAIL_MOTION_ENTITY = "mail_motion_entity"
CONF_MAIL_SLOT_ENTITY = "mail_slot_entity"
CONF_MAIL_ARRIVAL_ACTIONS = "mail_arrival_actions"
CONF_GROUP_ACTIONS = "group_actions"
CONF_DOOR_OPEN_ACTIONS = "door_open_actions"
CONF_LOCK_LOCKED_ACTIONS = "lock_locked_actions"
CONF_LOCK_UNLOCKED_ACTIONS = "lock_unlocked_actions"
CONF_SHUTTER_OPEN_ACTIONS = "shutter_open_actions"
CONF_SHUTTER_CLOSE_ACTIONS = "shutter_close_actions"
CONF_COMPRESSOR_INACTIVE_ACTIONS = "compressor_inactive_actions"
CONF_PLUG_OFF_ACTIONS = "plug_off_actions"
CONF_DOOR_OPEN_DELAY_SECONDS = "door_open_delay_seconds"
CONF_COMPRESSOR_INACTIVE_DELAY_SECONDS = "compressor_inactive_delay_seconds"
CONF_PLUG_OFF_REPEAT_INTERVAL_SECONDS = "plug_off_repeat_interval_seconds"
CONF_PLUG_OFF_REPEAT_COUNT = "plug_off_repeat_count"
CONF_ALARM_REPEAT_INTERVAL_SECONDS = "alarm_repeat_interval_seconds"
CONF_ALARM_REPEAT_COUNT = "alarm_repeat_count"
CONF_DOOR_ENTITY = "door_entity"
CONF_PLUG_ENTITY = "plug_entity"
CONF_START_POWER_W = "start_power_w"
CONF_START_DURATION_SECONDS = "start_duration_seconds"
CONF_FINISH_POWER_W = "finish_power_w"
CONF_FINISH_DURATION_SECONDS = "finish_duration_seconds"
CONF_MAX_RUNTIME_SECONDS = "max_runtime_seconds"
CONF_START_ACTIONS = "start_actions"
CONF_FINISH_ACTIONS = "finish_actions"
CONF_EMPTIED_ACTIONS = "emptied_actions"
CONF_MAX_RUNTIME_ACTIONS = "max_runtime_actions"
CONF_PENDING_ACTIONS = "pending_actions"
CONF_PENDING_DELAY_SECONDS = "pending_delay_seconds"
CONF_PENDING_INTERVAL_SECONDS = "pending_interval_seconds"
CONF_PENDING_REPEATS = "pending_repeats"

ACTION_GROUP_CONFIG_KEYS = {
	"cycle_start": CONF_START_ACTIONS,
	"cycle_finish": CONF_FINISH_ACTIONS,
	"emptied": CONF_EMPTIED_ACTIONS,
	"max_runtime": CONF_MAX_RUNTIME_ACTIONS,
	"pending_unload": CONF_PENDING_ACTIONS,
	"door_open_alarm": CONF_DOOR_OPEN_ACTIONS,
	"compressor_inactive_alarm": CONF_COMPRESSOR_INACTIVE_ACTIONS,
	"plug_off_alarm": CONF_PLUG_OFF_ACTIONS,
	"lock_locked": CONF_LOCK_LOCKED_ACTIONS,
	"lock_unlocked": CONF_LOCK_UNLOCKED_ACTIONS,
	"shutter_open": CONF_SHUTTER_OPEN_ACTIONS,
	"shutter_close": CONF_SHUTTER_CLOSE_ACTIONS,
}

DEFAULT_START_POWER_W = 4.0
DEFAULT_START_DURATION_SECONDS = 15
DEFAULT_FINISH_POWER_W = 1.0
DEFAULT_FINISH_DURATION_SECONDS = 60
DEFAULT_PENDING_DELAY_SECONDS = 900
DEFAULT_PENDING_INTERVAL_SECONDS = 900
DEFAULT_PENDING_REPEATS = 3
DEFAULT_DOOR_OPEN_DELAY_SECONDS = 120
DEFAULT_COMPRESSOR_INACTIVE_DELAY_SECONDS = 3600
DEFAULT_ALARM_REPEAT_INTERVAL_SECONDS = 900
DEFAULT_ALARM_REPEAT_COUNT = 3
DEFAULT_PLUG_OFF_REPEAT_INTERVAL_SECONDS = 900
DEFAULT_PLUG_OFF_REPEAT_COUNT = 3
