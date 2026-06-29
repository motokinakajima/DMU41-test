import argparse
import multiprocessing
import serial
import time
import os
from datetime import datetime

# ==========================================
# 1. Constants & Default Settings
# ==========================================
DEFAULT_BAUDRATE = 921600
BUFFER_SIZE = 16384  # 16KB buffer size for safety and SD protection

# Custom fixed symlinks for your udev rules
PORT_DMU = "/dev/imu_dmu"
PORT_SPRESENSE = "/dev/imu_spresense"
PORT_BNO = "/dev/imu_bno"

# Pre-defined headers as raw bytes
CSV_HEADER = b"micros,step,gx,gy,gz,ax,ay,az,temp\n"

# ==========================================
# 2. Worker Process (Data Logging Core)
# ==========================================
def logger_worker(port, baudrate, filepath, stop_event, record_event, buffer_size, header=None):
    try:
        with serial.Serial(
            port=port, baudrate=baudrate, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0
        ) as ser, open(filepath, 'wb') as f:
            
            if header:
                f.write(header)
                f.flush()
                
            buffer = bytearray()
            
            try:
                while not stop_event.is_set():
                    waiting = ser.in_waiting
                    if waiting > 0:
                        data = ser.read(waiting)
                        
                        if record_event.is_set():
                            buffer.extend(data)
                            
                            if len(buffer) >= buffer_size:
                                f.write(buffer)
                                f.flush()
                                buffer.clear()
                        else:
                            pass
                        # ---------------
                    else:
                        time.sleep(0.001)
                        
            except KeyboardInterrupt:
                pass
            
            if buffer:
                f.write(buffer)
                f.flush()
                
            try:
                ser.cancel_read()
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                time.sleep(0.1)
            except Exception:
                pass
                
    except Exception as e:
        print(f"\n[ERROR] Problem detected on port {port}: {e}")

# ==========================================
# 3. Main Orchestrator
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="3 IMU Multi-process Datalogger (ASCII Pure)")
    parser.add_argument('--name', type=str, default="", help="Optional name for the trial folder")
    parser.add_argument('--timer', type=int, default=120, help="Execution timer in minutes. Default is 120")
    parser.add_argument('--freq_dmu', type=int, default=1000, help="DMU sampling frequency (Hz)")
    parser.add_argument('--freq_spre', type=int, default=960, help="Spresense sampling frequency (Hz)")
    parser.add_argument('--freq_bno', type=int, default=100, help="BNO sampling frequency (Hz)")
    parser.add_argument('--notes', type=str, default="None provided.", help="Optional field notes for readme.md")
    parser.add_argument('--baudrate', type=int, default=DEFAULT_BAUDRATE, help="Serial baudrate")
    args = parser.parse_args()

    # --- Directory setup ---
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    dir_name = timestamp_str
    if args.name:
        # Filter spaces out to maintain safe pathing
        safe_name = args.name.replace(" ", "_")
        dir_name += f"_{safe_name}"
    
    # Resolves path directly inside a /results/ subdirectory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__line__ if '__file__' not in globals() else __file__))
    save_dir = os.path.join(script_dir, "results", dir_name)
    os.makedirs(save_dir, exist_ok=True)
    print(f"Target directory successfully created: {save_dir}")

    # --- Target File Paths ---
    file_dmu = os.path.join(save_dir, "dmu.bin")
    file_spre = os.path.join(save_dir, "spresense.csv")
    file_bno = os.path.join(save_dir, "bno.csv")
    file_readme = os.path.join(save_dir, "readme.md")

    # --- Generate readme.md ---
    with open(file_readme, 'w', encoding='ascii') as f:
        f.write(f"# IMU Trial Log\n\n")
        f.write(f"- **Start Time:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Optional Name:** {args.name if args.name else 'N/A'}\n")
        f.write(f"- **Duration (Timer):** {args.timer} minutes\n")
        f.write(f"- **Baudrate:** {args.baudrate} bps\n\n")
        f.write(f"## Sensor Frequencies\n")
        f.write(f"- DMU: {args.freq_dmu} Hz\n")
        f.write(f"- Spresense: {args.freq_spre} Hz\n")
        f.write(f"- BNO: {args.freq_bno} Hz\n\n")
        f.write(f"## Optional Notes\n")
        f.write(f"{args.notes}\n")

    # --- Multi-processing Initialization ---
    stop_event = multiprocessing.Event()
    record_event = multiprocessing.Event()  # 追加：記録開始の合図用
    
    p_dmu = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_DMU, args.baudrate, file_dmu, stop_event, record_event, BUFFER_SIZE, None)
    )
    p_spre = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_SPRESENSE, args.baudrate, file_spre, stop_event, record_event, BUFFER_SIZE, CSV_HEADER)
    )
    p_bno = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_BNO, args.baudrate, file_bno, stop_event, record_event, BUFFER_SIZE, CSV_HEADER)
    )

    print("Launching all logger subprocesses concurrently...")
    p_dmu.start()
    p_spre.start()
    p_bno.start()

    # --- Serial Warmup ---
    WARMUP_SECONDS = 5
    print(f"[INFO] Letting sensors boot and stabilize for {WARMUP_SECONDS} seconds...")
    time.sleep(WARMUP_SECONDS)
    
    # --- Synced Recording ---
    print("[INFO] GO! Signaling all processes to start recording.")
    record_event.set()


    # --- Main Timer Loop ---
    duration_sec = args.timer * 60
    start_time = time.time()
    last_report_time = start_time
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            if elapsed >= duration_sec:
                print(f"\n[INFO] Time limit reached ({args.timer} minutes). Stopping trial.")
                break
            
            remain = int(duration_sec - elapsed)
            
            # Print status every 20 seconds for all three IMUs
            if current_time - last_report_time >= 20.0:
                def get_kb(path):
                    try:
                        return os.path.getsize(path) / 1024.0
                    except OSError:
                        return 0.0
                
                kb_dmu = get_kb(file_dmu)
                kb_spre = get_kb(file_spre)
                kb_bno = get_kb(file_bno)
                
                print(f"\n[STATUS] Time left: {remain // 60}m {remain % 60}s | DMU: {kb_dmu:.1f} KB | SPRE: {kb_spre:.1f} KB | BNO: {kb_bno:.1f} KB")
                last_report_time = current_time
            
            # The extra spaces at the end ensure previous longer lines are overwritten completely
            print(f"\rTime Remaining: {remain // 60}m {remain % 60}s ...    ", end="", flush=True)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C detected. Initiating manual graceful shutdown.")

    # --- Graceful Shutdown Sequence ---
    print("\nStopping processes and flushing memory buffers to disk...")
    stop_event.set()

    # Explicitly waiting for each process to finish file operations safely
    if 'p_dmu' in locals() and p_dmu.is_alive():
        p_dmu.join()
    if 'p_spre' in locals() and p_spre.is_alive():
        p_spre.join()
    if 'p_bno' in locals() and p_bno.is_alive():
        p_bno.join()

    print("All data streams safely preserved. Execution complete.")

if __name__ == "__main__":
    main()