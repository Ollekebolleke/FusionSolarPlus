"""FusionSolar Scheduling Analysis device handler."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity

from ...device_handler import BaseDeviceHandler


class SchedulingAnalysisDeviceHandler(BaseDeviceHandler):
    """Handle FusionSolar SmartEMO Scheduling Analysis."""

    async def create_coordinator(self) -> DataUpdateCoordinator:
        """Create and return the Scheduling Analysis coordinator."""
        coordinator = DataUpdateCoordinator(
            self.hass,
            logging.getLogger(__name__),
            name=f"{self.device_name} FusionSolar Energy Management Assistant",
            update_method=self._async_get_data,
            update_interval=timedelta(minutes=1),
        )
        await coordinator.async_config_entry_first_refresh()
        return coordinator

    async def _async_get_data(self) -> Dict[str, Any]:
        """Get Scheduling Analysis data."""

        async def get_scheduling_analysis(client):
            return await self.hass.async_add_executor_job(
                client.get_scheduling_analysis,
                self.device_id,
            )

        return await self._get_client_and_retry(get_scheduling_analysis)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        """Create Scheduling Analysis entities."""
        return [
            SchedulingAnalysisSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            )
        ]


class SchedulingAnalysisSensor(CoordinatorEntity, SensorEntity):
    """Sensor for FusionSolar SmartEMO Scheduling Analysis."""

    _attr_name = "Energy Management Assistant"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, device_info):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id = f"{device_id}_scheduling_analysis"

    @property
    def native_value(self):
        """Return the first available scheduling action."""
        card = self._current_or_next_card()

        if not card:
            return "No schedule"

        storage_msg = card.get("storageMsg")
        grid_msg = card.get("gridMsg")

        if storage_msg and grid_msg:
            return f"{storage_msg} | {grid_msg}"

        if storage_msg:
            return storage_msg

        if grid_msg:
            return grid_msg

        return "No schedule"

    @property
    def extra_state_attributes(self):
        """Return details of the Scheduling Analysis schedule."""
        data = self.coordinator.data
        if not data:
            return {
                "start_time": None,
                "end_time": None,
                "storage_msg": None,
                "grid_msg": None,
                "description": None,
                "schedules": [],
            }

        cards = data.get("data", {}).get("cards", [])
        schedules = [card for card in cards if card is not None]

        card = self._current_or_next_card()

        return {
            "start_time": card.get("startTime") if card else None,
            "end_time": card.get("endTime") if card else None,
            "storage_msg": card.get("storageMsg") if card else None,
            "grid_msg": card.get("gridMsg") if card else None,
            "description": card.get("description") if card else None,
            "schedules": schedules,
        }

    def _parse_time(self, value: str) -> datetime | None:
        """Parse a FusionSolar Scheduling Analysis timestamp."""
        if not value:
            return None

        try:
            return datetime.strptime(
                value.removesuffix(" DST"),
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=ZoneInfo("Europe/Berlin"))
        except ValueError:
            return None

    def _current_or_next_card(self):
        """Return the current scheduling card, or the next future card."""
        data = self.coordinator.data
        if not data:
            return None

        cards = [
            card
            for card in data.get("data", {}).get("cards", [])
            if card is not None
        ]

        now = datetime.now(ZoneInfo("Europe/Berlin"))

        # First prefer a card that is active right now.
        for card in cards:
            start = self._parse_time(card.get("startTime"))
            end = self._parse_time(card.get("endTime"))

            if start and end and start <= now < end:
                return card

        # If there is no active card, return the next future card.
        future_cards = []

        for card in cards:
            start = self._parse_time(card.get("startTime"))

            if start and start > now:
                future_cards.append((start, card))

        if future_cards:
            return min(future_cards, key=lambda item: item[0])[1]

        return None

    @property
    def available(self):
        """Return whether Scheduling Analysis data is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
