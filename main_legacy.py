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
PORT_DMU = "COM5"
PORT_SPRESENSE = "/dev/imu_spresense"
PORT_BNO = "/dev/imu_bno"

# Pre-defined headers as raw bytes
CSV_HEADER = b"micros,step,gx,gy,gz,ax,ay,az,temp\n"

# ==========================================
# 2. Worker Process (Data Logging Core)
# ==========================================
def logger_worker(port, baudrate, filepath, stop_event, buffer_size, header=None):
    """
    Reads data from the serial port, buffers it in memory, and flushes to disk.
    Handles all streams as raw bytes (wb) for maximum speed and zero CPU overhead.
    """
    try:
        with serial.Serial(port, baudrate, timeout=0.1) as ser, open(filepath, 'wb') as f:
            # Write header if provided (only for Spresense and BNO CSVs)
            if header:
                f.write(header)
                f.flush()
                
            buffer = bytearray()
            
            while not stop_event.is_set():
                if ser.in_waiting > 0:
                    # Read all available bytes from the serial buffer
                    data = ser.read(ser.in_waiting)
                    buffer.extend(data)
                    
                    # Flush to disk once the buffer hits 16KB
                    if len(buffer) >= buffer_size:
                        f.write(buffer)
                        f.flush()
                        buffer.clear()
                else:
                    # Tiny sleep to keep CPU utilization close to 0%
                    time.sleep(0.001)
                    
            # Graceful shutdown: Write any remaining bytes left in the buffer
            if buffer:
                f.write(buffer)
                f.flush()
                
    except Exception as e:
        print(f"\n[ERROR] Problem detected on port {port}: {e}")

# ==========================================
# 3. Main Orchestrator
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="3 IMU Multi-process Datalogger (ASCII Pure)")
    parser.add_argument('--name', type=str, default="", help="Optional name for the trial folder")
    parser.add_argument('--timer', type=int, default=120, help="Execution timer in minutes. Default is 120")
    parser.add_argument('--freq_dmu', type=int, default=100, help="DMU sampling frequency (Hz)")
    parser.add_argument('--freq_spre', type=int, default=100, help="Spresense sampling frequency (Hz)")
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
    
    # Explicit process assignment for absolute code readability and friendliness
    p_dmu = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_DMU, args.baudrate, file_dmu, stop_event, BUFFER_SIZE, None)
    )
    p_spre = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_SPRESENSE, args.baudrate, file_spre, stop_event, BUFFER_SIZE, CSV_HEADER)
    )
    p_bno = multiprocessing.Process(
        target=logger_worker, 
        args=(PORT_BNO, args.baudrate, file_bno, stop_event, BUFFER_SIZE, CSV_HEADER)
    )

    print("Launching all logger subprocesses concurrently...")
    p_dmu.start()
    #p_spre.start()
    #p_bno.start()

    # --- Main Timer Loop ---
    duration_sec = args.timer * 60
    start_time = time.time()
    
    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration_sec:
                print(f"\nTime limit reached ({args.timer} minutes). Stopping trial.")
                break
            
            remain = int(duration_sec - elapsed)
            print(f"\rTime Remaining: {remain // 60}m {remain % 60}s ... ", end="", flush=True)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Initiating manual graceful shutdown.")

    # --- Graceful Shutdown Sequence ---
    print("\nStopping processes and flushing memory buffers to disk...")
    stop_event.set()

    # Explicitly waiting for each process to finish file operations safely
    p_dmu.join()
    p_spre.join()
    p_bno.join()

    print("All data streams safely preserved. Execution complete.")

if __name__ == "__main__":
    main()