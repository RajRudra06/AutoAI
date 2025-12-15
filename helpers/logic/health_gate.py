from typing import Dict, Tuple, List

# ----------------------------
# Domain thresholds (v1)
# ----------------------------
ENGINE_TEMP_HIGH = 105          # °C
BRAKE_WEAR_HIGH = 0.80          # 80%
BATTERY_LOW = 35                # %
VIBRATION_HIGH = 0.70           

ENGINE_TEMP_SPIKE = 15          # °C jump
BRAKE_WEAR_SPIKE = 0.20         # 20% jump


def needs_diagnosis(
    telemetry: Dict,
    previous_telemetry: Dict | None = None
) -> Tuple[bool, List[str]]:

    reasons: List[str] = []

    # ----------------------------
    # Read current values safely
    # ----------------------------
    engine_temp = telemetry.get("engine_temp", 0)
    brake_wear = telemetry.get("brake_wear", 0)
    battery = telemetry.get("battery_health", 100)
    vibration = telemetry.get("vibration", 0)

    # ----------------------------
    # Absolute thresholds
    # ----------------------------
    if engine_temp > ENGINE_TEMP_HIGH:
        reasons.append("engine_temp_high")

    if brake_wear > BRAKE_WEAR_HIGH:
        reasons.append("brake_wear_critical")

    if battery < BATTERY_LOW:
        reasons.append("battery_low")

    if vibration > VIBRATION_HIGH:
        reasons.append("high_vibration")

    # ----------------------------
    # Trend-based checks (if history exists)
    # ----------------------------
    if previous_telemetry:
        prev_temp = previous_telemetry.get("engine_temp")
        if prev_temp is not None and engine_temp - prev_temp > ENGINE_TEMP_SPIKE:
            reasons.append("engine_temp_spike")

        prev_brake = previous_telemetry.get("brake_wear")
        if prev_brake is not None and brake_wear - prev_brake > BRAKE_WEAR_SPIKE:
            reasons.append("brake_wear_spike")

    # ----------------------------
    # Decision
    # ----------------------------
    return len(reasons) > 0, reasons
