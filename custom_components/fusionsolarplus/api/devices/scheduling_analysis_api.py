"""FusionSolar Scheduling Analysis API."""

from datetime import datetime
from zoneinfo import ZoneInfo

from ..exceptions import FusionSolarException


SCHEDULING_ANALYSIS_PATH = (
    "/rest/dp/pvms/dpaiplugin/v1/aifc/"
    "scheduling-analysis/web/cards"
)


def get_scheduling_analysis(client, plant_dn: str) -> dict:
    """Get the SmartEMO Scheduling Analysis cards for a plant."""

    timezone = ZoneInfo("Europe/Berlin")
    now = datetime.now(timezone)
    offset_minutes = int(
        now.utcoffset().total_seconds() / 60
    )

    url = (
        f"https://{client._huawei_subdomain}.fusionsolar.huawei.com"
        f"{SCHEDULING_ANALYSIS_PATH}"
    )

    params = {
        "plantDn": plant_dn,
        "timeZone": offset_minutes // 60,
        "timeZoneStr": "Europe/Berlin",
    }

    headers = {
        "x-non-renewal-session": "true",
        "x-timezone-offset": str(offset_minutes),
    }

    response = client._session.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        raise FusionSolarException(
            f"Scheduling Analysis request failed: "
            f"HTTP {response.status_code}"
        )

    data = response.json()

    if data.get("code") != 0:
        raise FusionSolarException(
            f"Scheduling Analysis API error: "
            f"{data.get('message', 'Unknown error')}"
        )

    return data
