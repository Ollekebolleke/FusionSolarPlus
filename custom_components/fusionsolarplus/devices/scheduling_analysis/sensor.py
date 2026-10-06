"""FusionSolar Scheduling Analysis device handler."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from ...device_handler import BaseDeviceHandler


def _parse_time(value: str) -> datetime | None:
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
        """Get Scheduling Analysis and benefit data."""

        async def get_data(client):
            scheduling_analysis = await self.hass.async_add_executor_job(
                client.get_scheduling_analysis,
                self.device_id,
            )

            ai_revenue = await self.hass.async_add_executor_job(
                client.get_ai_revenue,
                self.device_id,
            )

            return {
                "scheduling_analysis": scheduling_analysis,
                "ai_revenue": ai_revenue,
            }

        return await self._get_client_and_retry(get_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        """Create Scheduling Analysis entities."""
        return [
            SchedulingAnalysisSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            ActualESScheduleSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            BenefitDaysElapsedSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            BenefitIncreaseRateSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            TotalBenefitIncreaseSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            DefaultPoliciesBenefitSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
            EnergyManagementAssistantBenefitSensor(
                coordinator=coordinator,
                device_info=self.device_info,
            ),
        ]


class SchedulingAnalysisSensor(CoordinatorEntity, SensorEntity):
    """Sensor for FusionSolar SmartEMO Scheduling Analysis."""

    _attr_name = "Scheduling Analysis"
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

        scheduling_data = data.get("scheduling_analysis", {})
        cards = scheduling_data.get("data", {}).get("cards", [])
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

    def _current_or_next_card(self):
        """Return the current scheduling card, or the next future card."""
        data = self.coordinator.data
        if not data:
            return None

        scheduling_data = data.get("scheduling_analysis", {})
        cards = [
            card
            for card in scheduling_data.get("data", {}).get("cards", [])
            if card is not None
        ]

        now = datetime.now(ZoneInfo("Europe/Berlin"))

        # First prefer a card that is active right now.
        for card in cards:
            start = _parse_time(card.get("startTime"))
            end = _parse_time(card.get("endTime"))

            if start and end and start <= now < end:
                return card

        # If there is no active card, return the next future card.
        future_cards = []

        for card in cards:
            start = _parse_time(card.get("startTime"))

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


class ActualESScheduleSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the currently active FusionSolar ESS schedule."""

    _attr_name = "Actual ESS Schedule"
    _attr_icon = "mdi:battery-clock-outline"

    def __init__(self, coordinator, device_info):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id = f"{device_id}_actual_ess_schedule"

    @property
    def native_value(self):
        """Return the currently active ESS schedule."""
        card = self._active_card()

        if not card:
            return "No active schedule"

        storage_msg = card.get("storageMsg")
        grid_msg = card.get("gridMsg")

        if storage_msg:
            return storage_msg

        if grid_msg:
            return grid_msg

        return "Active"

    @property
    def extra_state_attributes(self):
        """Return details of the currently active ESS schedule."""
        card = self._active_card()

        if not card:
            return {
                "start_time": None,
                "end_time": None,
                "storage_msg": None,
                "grid_msg": None,
                "description": None,
            }

        start = _parse_time(card.get("startTime"))
        end = _parse_time(card.get("endTime"))

        return {
            "start_time": start.isoformat() if start else None,
            "end_time": end.isoformat() if end else None,
            "storage_msg": card.get("storageMsg"),
            "grid_msg": card.get("gridMsg"),
            "description": card.get("description"),
        }

    def _active_card(self):
        """Return the scheduling card that is active right now."""
        data = self.coordinator.data
        if not data:
            return None

        scheduling_data = data.get("scheduling_analysis", {})
        cards = [
            card
            for card in scheduling_data.get("data", {}).get("cards", [])
            if card is not None
        ]

        now = datetime.now(ZoneInfo("Europe/Berlin"))

        for card in cards:
            start = _parse_time(card.get("startTime"))
            end = _parse_time(card.get("endTime"))

            if start and end and start <= now < end:
                return card

        return None

    @property
    def available(self):
        """Return whether Scheduling Analysis data is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )


class BenefitSensorBase(CoordinatorEntity, SensorEntity):
    """Base sensor for Energy Management Assistant benefit data."""

    def __init__(self, coordinator, device_info, unique_id_suffix):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id = f"{device_id}_{unique_id_suffix}"

    @property
    def available(self):
        """Return whether benefit data is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get("ai_revenue") is not None
        )


class BenefitDaysElapsedSensor(BenefitSensorBase):
    """Sensor for Energy Management Assistant elapsed days."""

    _attr_name = "Days elapsed"
    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator, device_info):
        super().__init__(
            coordinator,
            device_info,
            "benefit_days_elapsed",
        )

    @property
    def native_value(self):
        """Return the number of elapsed days."""
        return self.coordinator.data.get("ai_revenue", {}).get("days_elapsed")


class BenefitIncreaseRateSensor(BenefitSensorBase):
    """Sensor for Energy Management Assistant benefit increase rate."""

    _attr_name = "Total benefit increase rate"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, device_info):
        super().__init__(
            coordinator,
            device_info,
            "benefit_increase_rate",
        )

    @property
    def native_value(self):
        """Return the total benefit increase rate."""
        return self.coordinator.data.get("ai_revenue", {}).get(
            "total_benefit_increase_rate"
        )


class TotalBenefitIncreaseSensor(BenefitSensorBase):
    """Sensor for Energy Management Assistant total benefit increase."""

    _attr_name = "Total benefit increase"
    _attr_icon = "mdi:cash-plus"
    _attr_native_unit_of_measurement = "€"

    def __init__(self, coordinator, device_info):
        super().__init__(
            coordinator,
            device_info,
            "total_benefit_increase",
        )

    @property
    def native_value(self):
        """Return the total benefit increase."""
        return self.coordinator.data.get("ai_revenue", {}).get(
            "total_benefit_increase"
        )


class DefaultPoliciesBenefitSensor(BenefitSensorBase):
    """Sensor for Energy Management Assistant default policy benefit."""

    _attr_name = "Benefit under default policies"
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = "€"

    def __init__(self, coordinator, device_info):
        super().__init__(
            coordinator,
            device_info,
            "benefit_under_default_policies",
        )

    @property
    def native_value(self):
        """Return the benefit under default policies."""
        return self.coordinator.data.get("ai_revenue", {}).get(
            "benefit_under_default_policies"
        )


class EnergyManagementAssistantBenefitSensor(BenefitSensorBase):
    """Sensor for Energy Management Assistant benefit."""

    _attr_name = "Benefit with Energy Management Assistant"
    _attr_icon = "mdi:cash-plus"
    _attr_native_unit_of_measurement = "€"

    def __init__(self, coordinator, device_info):
        super().__init__(
            coordinator,
            device_info,
            "benefit_with_energy_management_assistant",
        )

    @property
    def native_value(self):
        """Return the benefit with Energy Management Assistant."""
        return self.coordinator.data.get("ai_revenue", {}).get(
            "benefit_with_energy_management_assistant"
        )
