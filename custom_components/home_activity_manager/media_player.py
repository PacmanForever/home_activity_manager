"""Media-player proxy for Home Activity Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MEDIA_PLAYER_ENTITY
from .entity_proxy import (
    EntityProxyMixin,
    remove_proxy_entity,
    use_source_entity_on_appliance,
)
from .runtime import ApplianceRuntime, entry_runtimes


_STANDARD_ATTRIBUTES = {
    "app_id",
    "app_name",
    "device_class",
    "group_members",
    "is_volume_muted",
    "media_album_artist",
    "media_album_name",
    "media_artist",
    "media_channel",
    "media_content_id",
    "media_content_type",
    "media_duration",
    "media_episode",
    "media_image_remotely_accessible",
    "media_image_url",
    "media_playlist",
    "media_position",
    "media_position_updated_at",
    "media_season",
    "media_series_title",
    "media_title",
    "media_track",
    "repeat",
    "shuffle",
    "sound_mode",
    "sound_mode_list",
    "source",
    "source_list",
    "supported_features",
    "volume_level",
    "volume_step",
}


class ApplianceMediaPlayerProxy(EntityProxyMixin, MediaPlayerEntity):
    """Mirror standard media-player state and forward supported controls."""

    def __init__(self, runtime: ApplianceRuntime, entry: ConfigEntry) -> None:
        self._init_proxy(
            runtime,
            entry,
            runtime.config[CONF_MEDIA_PLAYER_ENTITY],
            "media_player",
            "media_player_proxy",
        )

    @property
    def state(self) -> MediaPlayerState | str | None:
        state = self._source_state
        if state is None:
            return None
        try:
            return MediaPlayerState(state.state)
        except ValueError:
            return state.state

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return MediaPlayerEntityFeature(self._number("supported_features") or 0)

    @property
    def device_class(self) -> str | None:
        return self._string("device_class")

    @property
    def app_id(self) -> str | None:
        return self._string("app_id")

    @property
    def app_name(self) -> str | None:
        return self._string("app_name")

    @property
    def media_content_id(self) -> str | None:
        return self._string("media_content_id")

    @property
    def media_content_type(self) -> str | None:
        return self._string("media_content_type")

    @property
    def media_duration(self) -> float | None:
        return self._number("media_duration")

    @property
    def media_position(self) -> float | None:
        return self._number("media_position")

    @property
    def media_position_updated_at(self) -> Any:
        return self._source_attribute("media_position_updated_at")

    @property
    def media_title(self) -> str | None:
        return self._string("media_title")

    @property
    def media_artist(self) -> str | None:
        return self._string("media_artist")

    @property
    def media_album_name(self) -> str | None:
        return self._string("media_album_name")

    @property
    def media_album_artist(self) -> str | None:
        return self._string("media_album_artist")

    @property
    def media_channel(self) -> str | None:
        return self._string("media_channel")

    @property
    def media_playlist(self) -> str | None:
        return self._string("media_playlist")

    @property
    def media_track(self) -> int | None:
        value = self._number("media_track")
        return int(value) if value is not None else None

    @property
    def media_series_title(self) -> str | None:
        return self._string("media_series_title")

    @property
    def media_season(self) -> str | None:
        return self._string("media_season")

    @property
    def media_episode(self) -> str | None:
        return self._string("media_episode")

    @property
    def media_image_url(self) -> str | None:
        return self._string("media_image_url")

    @property
    def media_image_remotely_accessible(self) -> bool:
        return self._source_attribute("media_image_remotely_accessible") is True

    @property
    def is_volume_muted(self) -> bool | None:
        value = self._source_attribute("is_volume_muted")
        return value if isinstance(value, bool) else None

    @property
    def volume_level(self) -> float | None:
        return self._number("volume_level")

    @property
    def volume_step(self) -> float | None:
        return self._number("volume_step")

    @property
    def source(self) -> str | None:
        return self._string("source")

    @property
    def source_list(self) -> list[str] | None:
        return self._string_list("source_list")

    @property
    def sound_mode(self) -> str | None:
        return self._string("sound_mode")

    @property
    def sound_mode_list(self) -> list[str] | None:
        return self._string_list("sound_mode_list")

    @property
    def shuffle(self) -> bool | None:
        value = self._source_attribute("shuffle")
        return value if isinstance(value, bool) else None

    @property
    def repeat(self) -> RepeatMode | str | None:
        value = self._string("repeat")
        if value is None:
            return None
        try:
            return RepeatMode(value)
        except ValueError:
            return value

    @property
    def group_members(self) -> list[str] | None:
        return self._string_list("group_members")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._proxy_attributes(_STANDARD_ATTRIBUTES)

    async def async_turn_on(self) -> None:
        await self._async_forward("media_player", "turn_on")

    async def async_turn_off(self) -> None:
        await self._async_forward("media_player", "turn_off")

    async def async_media_play(self) -> None:
        await self._async_forward("media_player", "media_play")

    async def async_media_pause(self) -> None:
        await self._async_forward("media_player", "media_pause")

    async def async_media_play_pause(self) -> None:
        await self._async_forward("media_player", "media_play_pause")

    async def async_media_stop(self) -> None:
        await self._async_forward("media_player", "media_stop")

    async def async_media_next_track(self) -> None:
        await self._async_forward("media_player", "media_next_track")

    async def async_media_previous_track(self) -> None:
        await self._async_forward("media_player", "media_previous_track")

    async def async_media_seek(self, position: float) -> None:
        await self._async_forward(
            "media_player", "media_seek", {"seek_position": position}
        )

    async def async_set_volume_level(self, volume: float) -> None:
        await self._async_forward(
            "media_player", "volume_set", {"volume_level": volume}
        )

    async def async_volume_up(self) -> None:
        await self._async_forward("media_player", "volume_up")

    async def async_volume_down(self) -> None:
        await self._async_forward("media_player", "volume_down")

    async def async_mute_volume(self, mute: bool) -> None:
        await self._async_forward(
            "media_player", "volume_mute", {"is_volume_muted": mute}
        )

    async def async_select_source(self, source: str) -> None:
        await self._async_forward("media_player", "select_source", {"source": source})

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self._async_forward(
            "media_player", "select_sound_mode", {"sound_mode": sound_mode}
        )

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        await self._async_forward(
            "media_player",
            "play_media",
            {
                "media_content_type": media_type,
                "media_content_id": media_id,
                **kwargs,
            },
        )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self._async_forward("media_player", "shuffle_set", {"shuffle": shuffle})

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        await self._async_forward("media_player", "repeat_set", {"repeat": repeat})

    async def async_join_players(self, group_members: list[str]) -> None:
        await self._async_forward(
            "media_player", "join", {"group_members": group_members}
        )

    async def async_unjoin_player(self) -> None:
        await self._async_forward("media_player", "unjoin")

    async def async_added_to_hass(self) -> None:
        await self._subscribe_to_runtime()

    def _number(self, key: str) -> float | None:
        value = self._source_attribute(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    def _string(self, key: str) -> str | None:
        value = self._source_attribute(key)
        return value if isinstance(value, str) else None

    def _string_list(self, key: str) -> list[str] | None:
        value = self._source_attribute(key)
        if not isinstance(value, (list, tuple)):
            return None
        return [item for item in value if isinstance(item, str)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    registry = er.async_get(hass)
    for runtime in entry_runtimes(entry):
        appliance_id = getattr(runtime, "appliance_id", entry.entry_id)
        source_entity_id = runtime.config.get(CONF_MEDIA_PLAYER_ENTITY)
        if source_entity_id and use_source_entity_on_appliance(
            hass, entry, runtime, source_entity_id
        ):
            remove_proxy_entity(registry, "media_player", appliance_id)
            continue
        if source_entity_id:
            async_add_entities([ApplianceMediaPlayerProxy(runtime, entry)])
            continue
        remove_proxy_entity(registry, "media_player", appliance_id)