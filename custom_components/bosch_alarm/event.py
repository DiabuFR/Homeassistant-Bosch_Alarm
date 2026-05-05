from bosch_alarm_mode2 import Panel
from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.helpers.device_registry import DeviceInfo
from . import BoschAlarmConfigEntry
from .const import DOMAIN

import re

B_G_Event_RE = re.compile(r"(\w+(?:\s\w+)*):\s(\d+)")

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
            name=f"Bosch {panel.model.name} Events",
            manufacturer="Bosch Security Systems",
        )
        # Track the last processed timestamp to avoid duplicates
        self._last_event_time = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to panel history updates."""
        # The library uses a standard observer pattern
        self._panel.history_observer.attach(self._handle_new_event)

    async def async_will_remove_from_hass(self) -> None:
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

        # Extract info from string
        # FIXME support other models
        msg = last_event.message

        event_summary = msg.split(",", 1)[0].strip()
        extracted_values = {match.group(1): int(match.group(2)) for match in B_G_Event_RE.finditer(last_event.message)}

        ha_event_type = _map_summary_to_type(event_summary)

        # Trigger the HA Event Sensor
        self._trigger_event(
            ha_event_type,
            {
                "timestamp": event_time,
                "raw": last_event.message,
                "type": event_summary,
                "area_id": extracted_values.get("Area"),
                "user_id": extracted_values.get("User ID"),
                "arm_state": extracted_values.get("Arm State"),
                "is_system_generated": extracted_values.get("User ID") == 65535
            }
        )
        self.async_write_ha_state()

def _map_summary_to_type(summary):
    """Maps the extracted header to one of our defined event_types."""
    summary = summary.lower()
    if "alarm" in summary:
        return "alarm"
    if "closing" in summary or "armed" in summary:
        return "arming"
    if "opening" in summary or "disarmed" in summary:
        return "disarming"
    if "fault" in summary or "trouble" in summary:
        return "trouble"
    return "history_event"