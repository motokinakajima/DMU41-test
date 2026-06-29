import serial
import sys

PORT = "/dev/imu_dmu"
BAUDRATE = 921600

print(f"Opening {PORT} at {BAUDRATE} bps...")
try:
    with serial.Serial(port=PORT, baudrate=BAUDRATE, timeout=1) as ser:
        print("Successfully opened! Streaming data (Press Ctrl+C to stop):\n")
        while True:
            # 1バイト読み込んでそのまま標準出力へ吐き出す
            data = ser.read(1)
            if data:
                sys.stdout.write(data.decode('ascii', errors='ignore'))
                sys.stdout.flush()
except KeyboardInterrupt:
    print("\nStopped by user.")
except Exception as e:
    print(f"\n[ERROR] {e}")