import serial
import time
import sys

# Configuration for the IMU ports
PORTS = {
    "DMU":  {"path": "/dev/imu_dmu",      "baud": 921600},
    "SPRE": {"path": "/dev/imu_spresense", "baud": 921600},
    "BNO":  {"path": "/dev/imu_bno",       "baud": 921600}
}
DURATION = 10  # Test duration in seconds

def main():
    print("=== IMU 10-Second Health Check ===")
    serials = {}
    counts = {"DMU": 0, "SPRE": 0, "BNO": 0}
    
    # 1. Initialize and open all ports safely
    for name, cfg in PORTS.items():
        try:
            serials[name] = serial.Serial(
                port=cfg["path"],
                baudrate=cfg["baud"],
                timeout=0  # Non-blocking mode
            )
            print(f"[ OK ] Opened {name} on {cfg['path']}")
        except Exception as e:
            print(f"[FAIL] Could not open {name}: {e}")
            serials[name] = None

    print("\n--- Monitoring Data Streams (10 Seconds) ---")
    start_time = time.time()
    last_report = start_time
    
    try:
        while time.time() - start_time < DURATION:
            current_time = time.time()
            
            # Read from all active serial ports
            for name, ser in serials.items():
                if ser is not None:
                    waiting = ser.in_waiting
                    if waiting > 0:
                        data = ser.read(waiting)
                        counts[name] += len(data)
            
            # Print status update every 1 second
            if current_time - last_report >= 1.0:
                elapsed = int(current_time - start_time)
                print(f"Elapsed: {elapsed:2d}s | DMU: {counts['DMU']:8d} B | SPRE: {counts['SPRE']:8d} B | BNO: {counts['BNO']:8d} B")
                last_report = current_time
                
            time.sleep(0.005)  # Lightweight nap to minimize CPU load
            
    except KeyboardInterrupt:
        print("\n[INFO] Health check manually stopped by user.")
        
    print("\n--- Graceful Port Teardown Sequence ---")
    # 2. Flush and close all ports to prevent driver lockups / zombie ports
    for name, ser in serials.items():
        if ser is not None:
            try:
                ser.cancel_read()
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.close()
                print(f"[CLEANED] {name} port safely closed.")
            except Exception as e:
                print(f"[WARN] Error tearing down {name}: {e}")
                
    print("\n=== Final Health Check Summary ===")
    all_healthy = True
    for name, total in counts.items():
        if total > 0:
            status = "OK (Streaming)"
        else:
            status = "DEAD (No Data Received)"
            all_healthy = False
        print(f" -> {name}: {total:8d} total bytes received | Status: {status}")
        
    if all_healthy:
        print("\nRESULT: All systems nominal! Ready for full trial.")
    else:
        print("\nRESULT: Check failed. Please investigate the dead sensor(s).")

if __name__ == "__main__":
    main()