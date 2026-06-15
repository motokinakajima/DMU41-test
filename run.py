#!/usr/bin/env python3
import argparse
import serial
import time

from dead_reckoning import deadReckoning as DeadReckoning
from parser import DMU41Parser


class DMU41:
    def __init__(self, port, baudrate=921600, output_hz=20, update_hz=1000):
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

    def _print_state(self):
        roll, pitch, yaw = self._dead_reckoning.angle
        x, y, z = self._dead_reckoning.position
        print(
            f"roll={roll:.6f} pitch={pitch:.6f} yaw={yaw:.6f} "
            f"x={x:.6f} y={y:.6f} z={z:.6f}",
            flush=True,
        )

    def update_reading(self):
        waiting = self._serial_port.in_waiting
        if waiting <= 0:
            time.sleep(0.001)
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
        while True:
            self.update_reading()
            now = time.time()
            if now - self._prev_print_time >= self._publish_period:
                self._print_state()
                self._prev_print_time = now


def main():
    parser = argparse.ArgumentParser(description="DMU41 serial reader")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=921600)
    parser.add_argument("--output-hz", type=float, default=20.0)
    parser.add_argument("--update-hz", type=float, default=1000.0)
    args = parser.parse_args()

    imu = DMU41(
        port=args.port,
        baudrate=args.baudrate,
        output_hz=args.output_hz,
        update_hz=args.update_hz,
    )
    imu.run()


if __name__ == '__main__':
    main()