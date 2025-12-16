from typing import List

def get_feature_names() -> List[str]:
    return [
        # ===== CURRENT STATE =====
        'engine_temp_c',
        'oil_pressure_psi',
        'brake_pad_mm',
        'battery_voltage_v',
        'vibration_level',
        'transmission_temp_c',
        'tire_pressure_avg',
        'tire_pressure_std',
        'tire_pressure_min',

        # ===== 7-DAY ROLLING STATS =====
        'engine_temp_mean_7d',
        'engine_temp_std_7d',
        'engine_temp_max_7d',
        'engine_temp_min_7d',
        'oil_pressure_mean_7d',
        'oil_pressure_std_7d',
        'oil_pressure_min_7d',
        'battery_voltage_mean_7d',
        'battery_voltage_min_7d',
        'coolant_temp_mean_7d',
        'coolant_temp_max_7d',
        'vibration_mean_7d',
        'vibration_max_7d',
        'transmission_temp_mean_7d',
        'transmission_temp_max_7d',

        # ===== DEGRADATION TRENDS =====
        'brake_wear_rate_30d',
        'oil_pressure_drop_rate_30d',
        'battery_voltage_drop_rate_30d',
        'vibration_increase_rate_30d',

        # ===== OPERATIONAL CONTEXT =====
        'miles_since_last_service',
        'avg_daily_miles_30d',
        'total_harsh_braking_7d',
        'total_harsh_acceleration_7d',
        'total_cold_starts_7d',
        'avg_fuel_consumption_7d',
        'avg_rpm_7d',
        'max_rpm_7d',

        # ===== DERIVED FEATURES =====
        'engine_stress_index',
        'cooling_efficiency',
        'brake_health_score',
        'battery_health_indicator',
        'temp_stability_score',
        'driving_aggression_score',
        'tire_balance_score'
    ]