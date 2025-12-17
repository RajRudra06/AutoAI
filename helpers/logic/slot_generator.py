from datetime import datetime, timedelta, timezone
import random

def generate_random_service_slot(days_ahead: int = 8) -> str:
  
    now = datetime.now(timezone.utc)

    # Random day within range
    day_offset = random.randint(1, days_ahead)
    service_date = now + timedelta(days=day_offset)

    # Random working hour
    hour = random.randint(9, 17)  # last slot starts at 5 PM
    minute = random.choice([0, 30])

    slot = service_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return slot.isoformat()
