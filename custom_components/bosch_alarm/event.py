from bosch_alarm_mode2 import Panel
from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.helpers.device_registry import DeviceInfo
from . import BoschAlarmConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up Bosch Alarm event entities."""
    # Official integration uses runtime_data to store the panel object
    panel = config_entry.runtime_data
    async_add_entities([BoschHistoryEventEntity(panel, config_entry)])


class BoschHistoryEventEntity(EventEntity):
    """Representation of a Bosch Alarm History Event."""

    _attr_icon = "mdi:clipboard-text-clock"
    _attr_device_class = None
    _attr_event_types = ["history_event"]
    _attr_has_entity_name = True
    _attr_translation_key = "history_log"

    def __init__(self, panel: Panel, entry: BoschAlarmConfigEntry) -> None:
        self._panel = panel
        self._attr_unique_id = f"{entry.entry_id}_history"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        # Track the last processed timestamp to avoid duplicates
        self._last_event_time = None

    async def async_added_to_hass(self):
        """Subscribe to panel history updates."""
        # The library uses a standard observer pattern
        self._panel.history_observer.attach(self._handle_new_event)

    async def async_will_remove_from_hass(self):
        """Unsubscribe when entity is removed."""
        self._panel.history_observer.detach(self._handle_new_event)

    def _handle_new_event(self):
        """Callback triggered by the bosch-alarm-mode2 library."""
        if not self._panel.events:
            return

        last_event = self._panel.events[-1]

        # Verify this is a new event based on the timestamp
        event_time = last_event.date.isoformat()
        if event_time == self._last_event_time:
            return

        self._last_event_time = event_time

        # Trigger the HA Event Sensor
        self._trigger_event(
            "history_event",
            {
                "timestamp": event_time,
                "event_code": last_event.event_code,
                "description": last_event.event_text,
                "area": last_event.area
            }
        )
        self.async_write_ha_state()