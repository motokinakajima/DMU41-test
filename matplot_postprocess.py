import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Plot merged IMU data from multiple sensors")
    parser.add_argument("experiment_name", type=str, help="Name of the experiment directory inside results/")
    parser.add_argument("--crop", "-c", type=float, default=None, help="Crop first N seconds of data")
    args = parser.parse_args()

    exp_dir = os.path.join("results", args.experiment_name)
    
    # GT入りのCSVがあれば優先的に読み込む
    gt_path = os.path.join(exp_dir, "postprocessing_with_gt.csv")
    base_path = os.path.join(exp_dir, "postprocessing.csv")
    
    if os.path.exists(gt_path):
        input_path = gt_path
        print(f"Found GT data: {gt_path}")
    else:
        input_path = base_path
        print(f"Using base data: {base_path}")

    # Create sub-directory if crop is specified
    if args.crop is not None:
        out_dir = os.path.join(exp_dir, f"crop_{args.crop}s")
        os.makedirs(out_dir, exist_ok=True)
        plot_path = os.path.join(out_dir, "sensor_comparison.png")
    else:
        plot_path = os.path.join(exp_dir, "sensor_comparison.png")

    pbar = tqdm(total=2, desc="Plotting Data")

    # 1. Load merged data
    df = pd.read_csv(input_path)
    
    # Crop data (elapsed_us is in microseconds)
    if args.crop is not None:
        df = df[df['elapsed_us'] <= (args.crop * 1000000.0)].reset_index(drop=True)
        
    pbar.update(1)

    # カラム名の互換性対応 (alignedがあればそちらを使う)
    def get_col(sensor, axis):
        aligned_col = f'g{axis}_{sensor}_aligned'
        base_col = f'g{axis}_{sensor}'
        return aligned_col if aligned_col in df.columns else base_col

    # 2. Matplotlib Visualization (4 subplots)
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    
    # Adjust time axis unit for readability when cropped
    if args.crop is not None and args.crop < 7200:
        time_series = df['elapsed_us'] / 1000000.0  # us to Seconds
        x_label = 'Time [seconds]'
    else:
        time_series = df['elapsed_us'] / 3600000000.0  # us to Hours
        x_label = 'Time [hours]'

    # Gyro X
    if get_col('dmu', 'x') in df.columns: axes[0].plot(time_series, df[get_col('dmu', 'x')], label='DMU41', color='crimson', alpha=0.7)
    if get_col('spre', 'x') in df.columns: axes[0].plot(time_series, df[get_col('spre', 'x')], label='Spresense', color='darkblue', alpha=0.7)
    if get_col('bno', 'x') in df.columns: axes[0].plot(time_series, df[get_col('bno', 'x')], label='BNO055', color='darkorange', alpha=0.7)
    if 'gx_gt' in df.columns: axes[0].plot(time_series, df['gx_gt'], label='Ground Truth', color='black', linewidth=1.5)
    axes[0].set_ylabel('Gyro X [deg/s]')
    axes[0].grid(True)
    axes[0].legend(loc='upper right')

    # Gyro Y
    if get_col('dmu', 'y') in df.columns: axes[1].plot(time_series, df[get_col('dmu', 'y')], label='DMU41', color='crimson', alpha=0.7)
    if get_col('spre', 'y') in df.columns: axes[1].plot(time_series, df[get_col('spre', 'y')], label='Spresense', color='darkblue', alpha=0.7)
    if get_col('bno', 'y') in df.columns: axes[1].plot(time_series, df[get_col('bno', 'y')], label='BNO055', color='darkorange', alpha=0.7)
    if 'gy_gt' in df.columns: axes[1].plot(time_series, df['gy_gt'], label='Ground Truth', color='black', linewidth=1.5)
    axes[1].set_ylabel('Gyro Y [deg/s]')
    axes[1].grid(True)

    # Gyro Z
    if get_col('dmu', 'z') in df.columns: axes[2].plot(time_series, df[get_col('dmu', 'z')], label='DMU41', color='crimson', alpha=0.7)
    if get_col('spre', 'z') in df.columns: axes[2].plot(time_series, df[get_col('spre', 'z')], label='Spresense', color='darkblue', alpha=0.7)
    if get_col('bno', 'z') in df.columns: axes[2].plot(time_series, df[get_col('bno', 'z')], label='BNO055', color='darkorange', alpha=0.7)
    if 'gz_gt' in df.columns: axes[2].plot(time_series, df['gz_gt'], label='Ground Truth', color='black', linewidth=1.5)
    axes[2].set_ylabel('Gyro Z [deg/s]')
    axes[2].grid(True)

    # Temperature (GT doesn't have temperature)
    if 'temp_dmu' in df.columns: axes[3].plot(time_series, df['temp_dmu'], label='DMU41', color='crimson', alpha=0.7)
    if 'temp_spre' in df.columns: axes[3].plot(time_series, df['temp_spre'], label='Spresense', color='darkblue', alpha=0.7)
    if 'temp_bno' in df.columns: axes[3].plot(time_series, df['temp_bno'], label='BNO055', color='darkorange', alpha=0.7)
    axes[3].set_ylabel('Temp [degC]')
    axes[3].set_xlabel(x_label)
    axes[3].grid(True)

    title_suffix = f" (First {args.crop}s)" if args.crop is not None else ""
    plt.suptitle(f"Sensor Comparison: {args.experiment_name}{title_suffix}")
    
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300)
    plt.close()
    pbar.update(1)
    
    pbar.close()
    print(f"Successfully saved plot to: {plot_path}")

if __name__ == "__main__":
    main()