#!/usr/bin/env python3
import argparse
import csv
import serial
import time
from pathlib import Path

from dead_reckoning import deadReckoning as DeadReckoning
from parser import DMU41Parser


class DMU41:
    def __init__(self, port, baudrate=921600, output_hz=20, update_hz=1000, csv_path=None):
        self._publish_period = 1 / output_hz
        self._update_period = 1 / update_hz
        self._serial_port = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
        )

        self._dead_reckoning = DeadReckoning()
        self._parser = DMU41Parser()
        self._prev_print_time = time.time()
        self._csv_path = Path(csv_path) if csv_path else None
        self._csv_file = None
        self._csv_writer = None
        self._csv_timestamp = 0.0
        self._csv_timestamp_step = 1 / 20.0

        if self._csv_path is not None:
            self._csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._csv_file = self._csv_path.open("w", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(
                self._csv_file,
                fieldnames=["timestamp", "roll", "pitch", "yaw", "x", "y", "z"],
            )
            self._csv_writer.writeheader()

    def close(self):
        if self._csv_file is not None:
            self._csv_file.close()

    def _print_state(self):
        roll, pitch, yaw = self._dead_reckoning.angle
        x, y, z = self._dead_reckoning.position
        message = (
            f"roll={roll:.6f} pitch={pitch:.6f} yaw={yaw:.6f} "
            f"x={x:.6f} y={y:.6f} z={z:.6f}"
        )
        print(message, flush=True)

        if self._csv_writer is not None:
            timestamp = self._csv_timestamp
            self._csv_writer.writerow(
                {
                    "timestamp": f"{timestamp:.6f}",
                    "roll": f"{roll:.6f}",
                    "pitch": f"{pitch:.6f}",
                    "yaw": f"{yaw:.6f}",
                    "x": f"{x:.6f}",
                    "y": f"{y:.6f}",
                    "z": f"{z:.6f}",
                }
            )
            self._csv_file.flush()
            self._csv_timestamp += self._csv_timestamp_step

    def update_reading(self):
        waiting = self._serial_port.in_waiting
        if waiting <= 0:
            time.sleep(0.00001)
            return

        data = self._serial_port.read(waiting)
        for byte in data:
            self.process_byte(byte)

    def process_byte(self, byte):
        raw_reading = self._parser.parse_byte_essential(byte)
        if raw_reading is None:
            return

        self._dead_reckoning.update(
            {
                "angular rates": raw_reading["angular rates"],
                "linear acceleration": raw_reading["linear accelerations"],
            },
            self._update_period,
        )

    def run(self):
        try:
            while True:
                self.update_reading()
                now = time.time()
                if now - self._prev_print_time >= self._publish_period:
                    self._print_state()
                    self._prev_print_time = now
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="DMU41 serial reader")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=921600)
    parser.add_argument("--output-hz", type=float, default=20.0)
    parser.add_argument("--update-hz", type=float, default=1000.0)
    parser.add_argument("--csv", dest="csv_path", default=None, help="CSV output path")
    args = parser.parse_args()

    imu = DMU41(
        port=args.port,
        baudrate=args.baudrate,
        output_hz=args.output_hz,
        update_hz=args.update_hz,
        csv_path=args.csv_path,
    )
    imu.run()


if __name__ == '__main__':
    main()