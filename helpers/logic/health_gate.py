# helpers/logic/health_gate.py
from typing import Dict, Tuple, List

# ----------------------------
# Thresholds on ENGINEERED FEATURES
# ----------------------------
ENGINE_TEMP_HIGH = 105
BRAKE_HEALTH_LOW = 5.5
BATTERY_HEALTH_LOW = 11.0
VIBRATION_HIGH = 1.2
ENGINE_STRESS_HIGH = 3.0


def needs_diagnosis(
    telemetry: Dict,
    previous_telemetry: Dict | None = None
) -> Tuple[bool, List[str]]:

    reasons: List[str] = []

    if not telemetry:
        return False, reasons

    # ----------------------------
    # Absolute checks (cheap)
    # ----------------------------
    if telemetry.get("engine_temp_c", 0) > ENGINE_TEMP_HIGH:
        reasons.append("engine_temp_high")

    if telemetry.get("brake_health_score", 10) < BRAKE_HEALTH_LOW:
        reasons.append("brake_health_low")

    if telemetry.get("battery_health_indicator", 15) < BATTERY_HEALTH_LOW:
        reasons.append("battery_health_low")

    if telemetry.get("vibration_level", 0) > VIBRATION_HIGH:
        reasons.append("high_vibration")

    if telemetry.get("engine_stress_index", 0) > ENGINE_STRESS_HIGH:
        reasons.append("engine_stress_high")

    # ----------------------------
    # Trend checks (optional)
    # ----------------------------
    if previous_telemetry:
        if (
            telemetry.get("engine_temp_mean_7d", 0)
            - previous_telemetry.get("engine_temp_mean_7d", 0)
            > 5
        ):
            reasons.append("engine_temp_trend_up")

    return len(reasons) > 0, reasons
