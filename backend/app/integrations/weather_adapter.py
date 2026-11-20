"""Grid-India weather portal adapter (mock). Areas are mapped to elements via their substation (TS p.134-135; FRD API-20)."""
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from datetime import timedelta

PHENOMENA = ["Thunderstorm with lightning", "Dust storm (wind 60-70 km/h)", "Heavy rainfall", "Dense fog", "Heat wave"]


def poll(db: Session) -> int:
    """Periodically fetch area alerts; the mock produces an alert for a random area about once every few polls."""
    from app.modules.master_registry.models import Substation
    from app.modules.realtime_outage.models import ScadaAlert

    recent = db.scalar(select(func.count()).select_from(ScadaAlert).where(ScadaAlert.source == "WEATHER",
                                                                           ScadaAlert.created_at >= utcnow() - timedelta(hours=3)))
    if recent and recent >= 3:
        return 0
    if random.random() > 0.35 and recent:
        return 0
    s = random.choice(db.scalars(select(Substation)).all())
    db.add(ScadaAlert(centre_id=s.centre_id, source="WEATHER", area=s.weather_area, severity="WARNING",
                      message=f"{random.choice(PHENOMENA)} expected over {s.weather_area} in next 6 hours"))
    return 1


def alerts_for_area(db: Session, area: str) -> list[str]:
    from app.modules.realtime_outage.models import ScadaAlert

    rows = db.scalars(select(ScadaAlert).where(ScadaAlert.source == "WEATHER", ScadaAlert.area == area,
                                               ScadaAlert.created_at >= utcnow() - timedelta(hours=12))).all()
    return [r.message for r in rows]
