#!/usr/bin/env python3
import argparse
import csv
import serial
import time
import numpy as np
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

        self._dead_reckoning = DeadReckoning(angular_bias=np.array([0.0, 0.0, 0.0]))
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
        # シリアルポートが開いていたら、ちゃんと閉じる（ここを追加！）
        if hasattr(self, '_serial_port') and self._serial_port is not None:
            try:
                self._serial_port.close()
                print("[INFO] シリアルポートを正常にクローズしました。")
            except Exception as e:
                print(f"[WARNING] シリアルポートのクローズ中にエラー: {e}")

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

    def run(self, duration=None):
        """
        duration: 実験時間（秒）。None の場合は Ctrl+C まで無限に回る
        """
        start_time = time.time()
        self._prev_print_time = start_time
        try:
            while True:
                self.update_reading()
                now = time.time()
                
                # タイマー判定：指定秒数が経過したらループを抜ける
                if duration is not None and (now - start_time) >= duration:
                    print(f"\n[INFO] 設定時間（{duration}秒）に達したため、このトライアルを終了します。")
                    break
                    
                if now - self._prev_print_time >= self._publish_period:
                    self._print_state()
                    self._prev_print_time = now
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="DMU41 serial reader with Auto-Timer & Multi-Trials")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=921600)
    parser.add_argument("--output-hz", type=float, default=20.0)
    parser.add_argument("--update-hz", type=float, default=1000.0)
    
    # 拡張した引数
    parser.add_argument("--prefix", default="trial", help="CSV出力のファイル名接頭辞 (e.g. 'trial' -> 'trial_001.csv')")
    parser.add_argument("--duration", type=float, default=60.0, help="1回あたりの実験時間（秒）。0を指定すると無限")
    parser.add_argument("--num-trials", type=int, default=3, help="実行するトライアルの総数")
    args = parser.parse_args()

    # duration が 0 以下の場合は無限ループ（従来通り）として扱う
    run_duration = args.duration if args.duration > 0 else None

    for trial_idx in range(1, args.num_trials + 1):
        # 3桁のゼロパディング（trial_001.csv, trial_002.csv ...）で自動生成
        csv_filename = f"{args.prefix}{trial_idx:03d}.csv"
        
        print("\n" + "="*60)
        print(f" トライアル開始 [{trial_idx} / {args.num_trials}]")
        print(f" 保存先ファイル: {csv_filename}")
        print(f" 計測時間: {args.duration if run_duration else '無限'} 秒")
        print("="*60)
        
        # 連続実験のときに、ちょっとIMUを置き直したり準備したりするインターバル
        if trial_idx > 1:
            print("次の実験の準備をしてください（IMUを完全に静止させてください）。")
            print("3秒後に自動で計測を開始します...")
            time.sleep(3)
        else:
            print("IMUを静止させてください。1秒後に開始します...")
            time.sleep(1)

        # 毎回新しくインスタンスを作ることで、内部のDeadReckoningインスタンスもリセットされる
        imu = DMU41(
            port=args.port,
            baudrate=args.baudrate,
            output_hz=args.output_hz,
            update_hz=args.update_hz,
            csv_path=csv_filename,
        )
        
        imu.run(duration=run_duration)
        
    print("\n[SUCCESS] すべての自動トライアルが正常に終了しました！")


if __name__ == '__main__':
    main()