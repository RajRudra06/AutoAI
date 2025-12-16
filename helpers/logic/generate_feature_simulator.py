import pandas as pd
import numpy as np
from typing import Dict, List


def extract_features_from_vehicle(vehicle_df: pd.DataFrame) -> Dict:
    # Ensure sorted by time
    vehicle_df = vehicle_df.sort_values('timestamp').reset_index(drop=True)

    if len(vehicle_df) < 10:
        raise ValueError(f"Insufficient data: only {len(vehicle_df)} records")

    latest = vehicle_df.iloc[-1]
    df_7d = vehicle_df.tail(28)
    df_all = vehicle_df

    features = {}

    # ===== CURRENT STATE =====
    features['engine_temp_c'] = latest['engine_temp_c']
    features['oil_pressure_psi'] = latest['oil_pressure_psi']
    features['brake_pad_mm'] = latest['brake_pad_mm']
    features['battery_voltage_v'] = latest['battery_voltage_v']
    features['vibration_level'] = latest['vibration_level']
    features['transmission_temp_c'] = latest['transmission_temp_c']

    tire_pressures = [
        latest['tire_pressure_fl'],
        latest['tire_pressure_fr'],
        latest['tire_pressure_rl'],
        latest['tire_pressure_rr']
    ]
    features['tire_pressure_avg'] = np.mean(tire_pressures)
    features['tire_pressure_std'] = np.std(tire_pressures)
    features['tire_pressure_min'] = np.min(tire_pressures)

    # ===== 7-DAY ROLLING STATS =====
    features['engine_temp_mean_7d'] = df_7d['engine_temp_c'].mean()
    features['engine_temp_std_7d'] = df_7d['engine_temp_c'].std()
    features['engine_temp_max_7d'] = df_7d['engine_temp_c'].max()
    features['engine_temp_min_7d'] = df_7d['engine_temp_c'].min()

    features['oil_pressure_mean_7d'] = df_7d['oil_pressure_psi'].mean()
    features['oil_pressure_std_7d'] = df_7d['oil_pressure_psi'].std()
    features['oil_pressure_min_7d'] = df_7d['oil_pressure_psi'].min()

    features['battery_voltage_mean_7d'] = df_7d['battery_voltage_v'].mean()
    features['battery_voltage_min_7d'] = df_7d['battery_voltage_v'].min()

    features['coolant_temp_mean_7d'] = df_7d['coolant_temp_c'].mean()
    features['coolant_temp_max_7d'] = df_7d['coolant_temp_c'].max()

    features['vibration_mean_7d'] = df_7d['vibration_level'].mean()
    features['vibration_max_7d'] = df_7d['vibration_level'].max()

    features['transmission_temp_mean_7d'] = df_7d['transmission_temp_c'].mean()
    features['transmission_temp_max_7d'] = df_7d['transmission_temp_c'].max()

    # ===== DEGRADATION TRENDS =====
    days_elapsed = max((df_all.iloc[-1]['timestamp'] - df_all.iloc[0]['timestamp']).days, 1)

    features['brake_wear_rate_30d'] = (
        df_all.iloc[0]['brake_pad_mm'] - df_all.iloc[-1]['brake_pad_mm']
    ) / days_elapsed

    features['oil_pressure_drop_rate_30d'] = (
        df_all.iloc[0]['oil_pressure_psi'] - df_all.iloc[-1]['oil_pressure_psi']
    ) / days_elapsed

    features['battery_voltage_drop_rate_30d'] = (
        df_all.iloc[0]['battery_voltage_v'] - df_all.iloc[-1]['battery_voltage_v']
    ) / days_elapsed

    features['vibration_increase_rate_30d'] = (
        df_all.iloc[-1]['vibration_level'] - df_all.iloc[0]['vibration_level']
    ) / days_elapsed

    # ===== OPERATIONAL CONTEXT =====
    features['miles_since_last_service'] = latest['miles_since_last_service']
    features['avg_daily_miles_30d'] = df_all['daily_miles'].mean()
    features['total_harsh_braking_7d'] = df_7d['harsh_braking_events'].sum()
    features['total_harsh_acceleration_7d'] = df_7d['harsh_acceleration_events'].sum()
    features['total_cold_starts_7d'] = df_7d['cold_starts'].sum()

    features['avg_fuel_consumption_7d'] = df_7d['fuel_consumption_l_per_100km'].mean()
    features['avg_rpm_7d'] = df_7d['engine_rpm'].mean()
    features['max_rpm_7d'] = df_7d['engine_rpm'].max()

    # ===== DERIVED =====
    features['engine_stress_index'] = features['engine_temp_c'] / max(features['oil_pressure_psi'], 1)
    features['cooling_efficiency'] = features['engine_temp_c'] - features['coolant_temp_mean_7d']
    features['brake_health_score'] = features['brake_pad_mm'] - (10 * features['brake_wear_rate_30d'])
    features['battery_health_indicator'] = features['battery_voltage_v'] - (
        100 * features['battery_voltage_drop_rate_30d']
    )
    features['temp_stability_score'] = 1 / (1 + features['engine_temp_std_7d'])

    total_harsh = features['total_harsh_braking_7d'] + features['total_harsh_acceleration_7d']
    features['driving_aggression_score'] = total_harsh / 7
    features['tire_balance_score'] = 1 / (1 + features['tire_pressure_std'])

    return features
