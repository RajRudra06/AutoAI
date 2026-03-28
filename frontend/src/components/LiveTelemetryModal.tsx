"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Activity, Zap, Gauge, Thermometer, Battery, Droplets, Disc, Cpu, Shield } from "lucide-react";
import styles from "@/app/vehicle/[id]/page.module.css";

interface LiveData {
  vehicle_id: string;
  timestamp: string;
  sensors: {
    speed_kmph: number;
    battery_percent: number;
    engine_temp_c: number;
    oil_health_percent: number;
    tire_pressure_psi: number;
    odometer_km: number;
    engine_rpm: number;
    fuel_level_percent: number;
    coolant_pressure_psi: number;
    intake_air_temp_c: number;
    throttle_pos_percent: number;
    brake_pad_wear_percent: number;
  };
}

interface Props {
  vehicleId: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function LiveTelemetryModal({ vehicleId, isOpen, onClose }: Props) {
  const [data, setData] = useState<LiveData | null>(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isOpen) {
      if (socketRef.current) {
        socketRef.current.close();
      }
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // Adjust this to your backend URL if different
    const wsUrl = `${protocol}//127.0.0.1:8000/api/telematics/ws/${vehicleId}`;
    
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        setData(parsed);
      } catch (err) {
        console.error("WS Parse Error:", err);
      }
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);

    return () => {
      socket.close();
    };
  }, [isOpen, vehicleId]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div 
        className={styles.liveStreamOverlay}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div 
          className={styles.liveStreamModal}
          initial={{ scale: 0.9, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.9, opacity: 0, y: 20 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
        >
          {/* Header */}
          <div className={styles.modalHeader}>
            <div className={styles.modalTitleArea}>
              <div className={styles.liveIndicator}>
                <div className={styles.liveDot} />
                LIVE STREAM
              </div>
              <h3>Telemetry Diagnostics: {vehicleId}</h3>
            </div>
            <button className={styles.closeModalBtn} onClick={onClose}>
              <X size={20} />
            </button>
          </div>

          {!connected ? (
            <div className={styles.modalLoading}>
              <Activity className={styles.spinIcon} />
              <p>Establishing secure WebSocket uplink...</p>
            </div>
          ) : !data ? (
            <div className={styles.modalLoading}>
              <Zap className={styles.pulseIcon} />
              <p>Waiting for data frames...</p>
            </div>
          ) : (
            <div className={styles.liveDataGrid}>
              <MetricCard 
                icon={<Gauge size={24} />} 
                label="SPEED" 
                value={data.sensors.speed_kmph} 
                unit="KMPH" 
                color="#06b6d4" 
              />
              <MetricCard 
                icon={<Battery size={24} />} 
                label="BATTERY" 
                value={data.sensors.battery_percent} 
                unit="%" 
                color="#10b981" 
              />
              <MetricCard 
                icon={<Thermometer size={24} />} 
                label="ENGINE TEMP" 
                value={data.sensors.engine_temp_c} 
                unit="°C" 
                color="#f87171" 
              />
               <MetricCard 
                icon={<Droplets size={24} />} 
                label="OIL HEALTH" 
                value={data.sensors.oil_health_percent} 
                unit="%" 
                color="#fbbf24" 
              />
               <MetricCard 
                icon={<Disc size={24} />} 
                label="TIRE PRESSURE" 
                value={data.sensors.tire_pressure_psi} 
                unit="PSI" 
                color="#818cf8" 
              />
               <MetricCard 
                icon={<Activity size={24} />} 
                label="ODOMETER" 
                value={data.sensors.odometer_km.toLocaleString()} 
                unit="KM" 
                color="#a78bfa" 
              />
              <MetricCard 
                icon={<Cpu size={24} />} 
                label="ENGINE RPM" 
                value={data.sensors.engine_rpm} 
                unit="RPM" 
                color="#f472b6" 
              />
              <MetricCard 
                icon={<Zap size={24} />} 
                label="FUEL LEVEL" 
                value={data.sensors.fuel_level_percent} 
                unit="%" 
                color="#fb923c" 
              />
              <MetricCard 
                icon={<Droplets size={24} />} 
                label="COOLANT PRESSURE" 
                value={data.sensors.coolant_pressure_psi} 
                unit="PSI" 
                color="#38bdf8" 
              />
              <MetricCard 
                icon={<Thermometer size={24} />} 
                label="INTAKE TEMP" 
                value={data.sensors.intake_air_temp_c} 
                unit="°C" 
                color="#4ade80" 
              />
              <MetricCard 
                icon={<Cpu size={24} />} 
                label="THROTTLE" 
                value={data.sensors.throttle_pos_percent} 
                unit="%" 
                color="#c084fc" 
              />
              <MetricCard 
                icon={<Shield size={24} />} 
                label="BRAKE WEAR" 
                value={data.sensors.brake_pad_wear_percent} 
                unit="%" 
                color="#94a3b8" 
              />
            </div>
          )}

          <div className={styles.modalFooter}>
            <div className={styles.statusPill}>
              <div className={styles.statusDotSmall} />
              Protocol: WSS 1.3
            </div>
            <div className={styles.timestampMono}>
              LAST_FRAME: {new Date(data?.timestamp || Date.now()).toLocaleTimeString()}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function MetricCard({ icon, label, value, unit, color }: any) {
  return (
    <div className={styles.liveMetricCard} style={{ "--accent": color } as any}>
      <div className={styles.metricIcon} style={{ color }}>{icon}</div>
      <div className={styles.metricContent}>
        <p className={styles.metricLabel}>{label}</p>
        <div className={styles.metricValueLine}>
          <span className={styles.metricValue}>{value}</span>
          <span className={styles.metricUnit}>{unit}</span>
        </div>
      </div>
      <div className={styles.metricGlow} style={{ background: color }} />
    </div>
  );
}
