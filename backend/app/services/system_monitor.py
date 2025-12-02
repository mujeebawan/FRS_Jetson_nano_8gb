"""
System Resource Monitor for Jetson Orin Nano.

Provides real-time CPU, GPU, RAM monitoring using tegrastats and standard Linux tools.
"""

import subprocess
import re
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class ResourceStats:
    """System resource statistics."""
    cpu_percent: float
    ram_used_mb: int
    ram_total_mb: int
    ram_percent: float
    gpu_percent: float
    gpu_freq_mhz: int
    gpu_temp_c: float
    cpu_temp_c: float
    power_watts: float


class SystemMonitor:
    """
    Monitor Jetson system resources.

    Uses tegrastats for GPU metrics and /proc for CPU/RAM.
    """

    def __init__(self):
        self._last_stats: Optional[ResourceStats] = None

    def get_stats(self) -> Dict[str, Any]:
        """Get current system resource statistics."""
        try:
            stats = {
                "cpu": self._get_cpu_stats(),
                "memory": self._get_memory_stats(),
                "gpu": self._get_gpu_stats(),
                "temperature": self._get_temperature(),
                "power": self._get_power()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                "error": str(e),
                "cpu": {"percent": 0},
                "memory": {"percent": 0, "used_mb": 0, "total_mb": 0},
                "gpu": {"percent": 0, "freq_mhz": 0},
                "temperature": {"cpu": 0, "gpu": 0},
                "power": {"watts": 0}
            }

    def _get_cpu_stats(self) -> Dict[str, Any]:
        """Get CPU usage statistics."""
        try:
            # Read /proc/stat for CPU usage
            with open('/proc/stat', 'r') as f:
                line = f.readline()

            # Parse CPU times
            parts = line.split()
            if parts[0] == 'cpu':
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle = int(parts[4])
                iowait = int(parts[5]) if len(parts) > 5 else 0

                total = user + nice + system + idle + iowait
                active = user + nice + system

                # Store for delta calculation
                if hasattr(self, '_last_cpu_total'):
                    total_delta = total - self._last_cpu_total
                    active_delta = active - self._last_cpu_active
                    percent = (active_delta / total_delta * 100) if total_delta > 0 else 0
                else:
                    percent = (active / total * 100) if total > 0 else 0

                self._last_cpu_total = total
                self._last_cpu_active = active

                # Get load average
                with open('/proc/loadavg', 'r') as f:
                    load = f.read().split()[:3]

                return {
                    "percent": round(percent, 1),
                    "cores": os.cpu_count() or 6,
                    "load_1m": float(load[0]),
                    "load_5m": float(load[1]),
                    "load_15m": float(load[2])
                }
        except Exception as e:
            logger.debug(f"CPU stats error: {e}")
            return {"percent": 0, "cores": 6, "load_1m": 0}

    def _get_memory_stats(self) -> Dict[str, Any]:
        """Get RAM usage statistics."""
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()

            # Parse meminfo
            total = self._parse_meminfo(meminfo, 'MemTotal')
            free = self._parse_meminfo(meminfo, 'MemFree')
            available = self._parse_meminfo(meminfo, 'MemAvailable')
            buffers = self._parse_meminfo(meminfo, 'Buffers')
            cached = self._parse_meminfo(meminfo, 'Cached')

            # Calculate used memory (exclude buffers/cache)
            used = total - available
            percent = (used / total * 100) if total > 0 else 0

            return {
                "used_mb": round(used / 1024),
                "total_mb": round(total / 1024),
                "available_mb": round(available / 1024),
                "percent": round(percent, 1),
                "cached_mb": round((buffers + cached) / 1024)
            }
        except Exception as e:
            logger.debug(f"Memory stats error: {e}")
            return {"used_mb": 0, "total_mb": 8192, "percent": 0}

    def _parse_meminfo(self, meminfo: str, key: str) -> int:
        """Parse a value from /proc/meminfo (returns kB)."""
        match = re.search(rf'{key}:\s+(\d+)', meminfo)
        return int(match.group(1)) if match else 0

    def _get_gpu_stats(self) -> Dict[str, Any]:
        """Get GPU usage using tegrastats or nvidia-smi."""
        try:
            # Try tegrastats first (Jetson-specific)
            result = subprocess.run(
                ['timeout', '1', 'tegrastats', '--interval', '100'],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.stdout:
                return self._parse_tegrastats(result.stdout)

        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"tegrastats error: {e}")

        # Fallback: try nvidia-smi
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.current.graphics',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                return {
                    "percent": float(parts[0].strip()),
                    "memory_used_mb": int(parts[1].strip()),
                    "memory_total_mb": int(parts[2].strip()),
                    "temp_c": float(parts[3].strip()),
                    "freq_mhz": int(parts[4].strip())
                }
        except Exception as e:
            logger.debug(f"nvidia-smi error: {e}")

        return {"percent": 0, "freq_mhz": 0, "memory_used_mb": 0, "memory_total_mb": 0}

    def _parse_tegrastats(self, output: str) -> Dict[str, Any]:
        """Parse tegrastats output for GPU metrics."""
        try:
            # Example: GR3D_FREQ 76% [email protected]
            gr3d_match = re.search(r'GR3D_FREQ\s+(\d+)%', output)
            gpu_percent = int(gr3d_match.group(1)) if gr3d_match else 0

            # GPU frequency
            freq_match = re.search(r'GR3D_FREQ\s+\d+%@(\d+)', output)
            gpu_freq = int(freq_match.group(1)) if freq_match else 0

            # GPU temperature
            gpu_temp_match = re.search(r'GPU@(\d+\.?\d*)C', output)
            gpu_temp = float(gpu_temp_match.group(1)) if gpu_temp_match else 0

            # RAM usage from tegrastats (more accurate for Jetson)
            ram_match = re.search(r'RAM\s+(\d+)/(\d+)MB', output)
            ram_used = int(ram_match.group(1)) if ram_match else 0
            ram_total = int(ram_match.group(2)) if ram_match else 0

            return {
                "percent": gpu_percent,
                "freq_mhz": gpu_freq,
                "memory_used_mb": ram_used,
                "memory_total_mb": ram_total,
                "temp_c": gpu_temp
            }
        except Exception as e:
            logger.debug(f"tegrastats parse error: {e}")
            return {"percent": 0, "freq_mhz": 0}

    def _get_temperature(self) -> Dict[str, float]:
        """Get CPU and GPU temperatures."""
        temps = {"cpu": 0.0, "gpu": 0.0}

        try:
            # Read thermal zones
            for i in range(10):
                zone_path = f'/sys/class/thermal/thermal_zone{i}'
                type_path = f'{zone_path}/type'
                temp_path = f'{zone_path}/temp'

                if os.path.exists(type_path) and os.path.exists(temp_path):
                    with open(type_path, 'r') as f:
                        zone_type = f.read().strip().lower()
                    with open(temp_path, 'r') as f:
                        temp = int(f.read().strip()) / 1000.0

                    if 'cpu' in zone_type or 'soc' in zone_type:
                        temps["cpu"] = max(temps["cpu"], temp)
                    elif 'gpu' in zone_type:
                        temps["gpu"] = max(temps["gpu"], temp)
        except Exception as e:
            logger.debug(f"Temperature read error: {e}")

        return temps

    def _get_power(self) -> Dict[str, float]:
        """Get power consumption (Jetson-specific)."""
        try:
            # Try reading from INA3221 power monitor
            power_paths = [
                '/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon*/in1_input',
                '/sys/bus/i2c/drivers/ina3221x/1-0040/iio:device0/in_power0_input'
            ]

            import glob
            for pattern in power_paths:
                matches = glob.glob(pattern)
                if matches:
                    with open(matches[0], 'r') as f:
                        # Convert mW to W
                        power_mw = int(f.read().strip())
                        return {"watts": round(power_mw / 1000.0, 2)}

            return {"watts": 0}
        except Exception as e:
            logger.debug(f"Power read error: {e}")
            return {"watts": 0}


# Singleton instance
_monitor: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """Get singleton system monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor
