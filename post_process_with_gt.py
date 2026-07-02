import argparse
import os
import pandas as pd
import numpy as np
from scipy import signal
from scipy.spatial.transform import Rotation
from scipy.interpolate import interp1d
from tqdm import tqdm

def lowpass_filter(data, cutoff, fs, order=4):
    """
    Apply a zero-phase Butterworth lowpass filter.
    """
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False) # type: ignore
    return signal.filtfilt(b, a, data)

def main():
    parser = argparse.ArgumentParser(description="Find offset using LPF, align coordinates, and merge GT with IMU data")
    parser.add_argument("experiment_name", type=str, help="Name of the experiment directory inside results/")
    args = parser.parse_args()

    exp_dir = os.path.join("results", args.experiment_name)
    gt_path = os.path.join(exp_dir, "gt.csv")
    imu_path = os.path.join(exp_dir, "postprocessing.csv")
    output_path = os.path.join(exp_dir, "postprocessing_with_gt.csv")
    readme_path = os.path.join(exp_dir, "README.md")

    if not os.path.exists(gt_path) or not os.path.exists(imu_path):
        print(f"Error: Could not find gt.csv or postprocessing.csv in {exp_dir}")
        return

    print("Loading datasets...")

    # ==========================================
    # 1. Parse GT (MoCap) Data & Defend against time jumps
    # ==========================================
    skip_rows = 0
    with open(gt_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if ',Timestamp' in line:
                skip_rows = i
                break
    
    df_gt = pd.read_csv(gt_path, skiprows=skip_rows)
    df_gt.columns = [col.strip() for col in df_gt.columns if isinstance(col, str)]
    
    t_gt_sec = ((df_gt['Timestamp'] - df_gt['Timestamp'].iloc[0]) / 1000.0).to_numpy(dtype=float)

    # Defend against GT time jumps (ghost data)
    dt_gt = np.diff(t_gt_sec)
    bad_gt_indices = np.where(dt_gt > 5.0)[0]
    if len(bad_gt_indices) > 0:
        cut_idx = bad_gt_indices[0] + 1
        print(f"[Warning] GT data time jump detected at index {cut_idx}. Truncating.")
        df_gt = df_gt.iloc[:cut_idx].copy()
        t_gt_sec = t_gt_sec[:cut_idx]

    fs_gt = 1.0 / np.mean(np.diff(t_gt_sec))

    quats = df_gt[['QxToGlobal1', 'QyToGlobal1', 'QzToGlobal1', 'QwToGlobal1']].to_numpy()
    rot = Rotation.from_quat(quats)
    euler_gt = rot.as_euler('ZYX', degrees=True)
    
    gt_angle_z = euler_gt[:, 0]
    gt_angle_y = euler_gt[:, 1]
    gt_angle_x = euler_gt[:, 2]

    gx_gt_raw = np.gradient(gt_angle_x, t_gt_sec)
    gy_gt_raw = np.gradient(gt_angle_y, t_gt_sec)
    gz_gt_raw = np.gradient(gt_angle_z, t_gt_sec)

    print(f"Applying LPF to GT data (FS: {fs_gt:.1f}Hz)...")
    cutoff_hz = 5.0
    gx_gt_clean = lowpass_filter(gx_gt_raw, cutoff=cutoff_hz, fs=fs_gt)
    gy_gt_clean = lowpass_filter(gy_gt_raw, cutoff=cutoff_hz, fs=fs_gt)
    gz_gt_clean = lowpass_filter(gz_gt_raw, cutoff=cutoff_hz, fs=fs_gt)

    # ==========================================
    # 2. Parse IMU Data & Defend against time jumps
    # ==========================================
    df_imu = pd.read_csv(imu_path)
    t_imu_sec = ((df_imu['elapsed_us'] - df_imu['elapsed_us'].iloc[0]) / 1e6).to_numpy(dtype=float)

    # Defend against IMU time jumps (ghost data)
    dt_imu = np.diff(t_imu_sec)
    bad_imu_indices = np.where(dt_imu > 5.0)[0]
    if len(bad_imu_indices) > 0:
        cut_idx = bad_imu_indices[0] + 1
        print(f"[Warning] IMU data time jump detected at index {cut_idx}. Truncating.")
        df_imu = df_imu.iloc[:cut_idx].copy()
        t_imu_sec = t_imu_sec[:cut_idx]

    # ==========================================
    # 3. Coordinate Alignment (IMU to GT frame)
    # ==========================================
    print("Aligning IMU coordinates...")
    
    # Adjust signs or swap axes here to match GT coordinate frame
    # e.g., df_imu['gx_dmu'] * -1.0
    df_imu['gx_dmu_aligned'] = df_imu['gy_dmu'] * 1.0
    df_imu['gy_dmu_aligned'] = df_imu['gx_dmu'] * 1.0
    df_imu['gz_dmu_aligned'] = df_imu['gz_dmu'] * -1.0

    df_imu['gx_spre_aligned'] = df_imu['gy_spre'] * 1.0
    df_imu['gy_spre_aligned'] = df_imu['gx_spre'] * 1.0
    df_imu['gz_spre_aligned'] = df_imu['gz_spre'] * -1.0

    df_imu['gx_bno_aligned'] = df_imu['gy_bno'] * 1.0
    df_imu['gy_bno_aligned'] = df_imu['gx_bno'] * 1.0
    df_imu['gz_bno_aligned'] = df_imu['gz_bno'] * -1.0

    gz_dmu_aligned_np = df_imu['gz_dmu_aligned'].to_numpy()

    # ==========================================
    # 4. Resample and Cross-Correlation (Coarse-to-Fine)
    # ==========================================
    print("Resampling and calculating coarse time offset...")
    target_fps = 100.0
    dt_resample = 1.0 / target_fps
    
    t_gt_resampled = np.arange(0, t_gt_sec[-1], dt_resample)
    t_imu_resampled = np.arange(0, t_imu_sec[-1], dt_resample)
    
    f_gt = interp1d(t_gt_sec, gz_gt_clean, bounds_error=False, fill_value="extrapolate") # type: ignore
    f_imu = interp1d(t_imu_sec, gz_dmu_aligned_np, bounds_error=False, fill_value="extrapolate") # type: ignore
    
    vel_gt_res = f_gt(t_gt_resampled)
    vel_imu_res_raw = f_imu(t_imu_resampled)
    
    vel_imu_res_filt = lowpass_filter(vel_imu_res_raw, cutoff=cutoff_hz, fs=target_fps)

    vel_gt_norm = (vel_gt_res - np.mean(vel_gt_res)) / (np.std(vel_gt_res) + 1e-6)
    vel_imu_norm = (vel_imu_res_filt - np.mean(vel_imu_res_filt)) / (np.std(vel_imu_res_filt) + 1e-6)

    # Step 1: Coarse Correlation (Full data)
    correlation_coarse = signal.correlate(vel_gt_norm, vel_imu_norm, mode='full')
    lags_coarse = signal.correlation_lags(len(vel_gt_norm), len(vel_imu_norm), mode='full')
    
    best_lag_coarse = lags_coarse[np.argmax(correlation_coarse)] 
    rough_offset_sec = best_lag_coarse * dt_resample 
    print(f"Rough Time Offset: {rough_offset_sec:.3f} seconds")

    # Step 2: Extract 20-second overlapping window based on rough offset
    if best_lag_coarse > 0:
        gt_overlap = vel_gt_norm[best_lag_coarse:]
        imu_overlap = vel_imu_norm[:-best_lag_coarse]
    elif best_lag_coarse < 0:
        gt_overlap = vel_gt_norm[:best_lag_coarse]
        imu_overlap = vel_imu_norm[-best_lag_coarse:]
    else:
        gt_overlap = vel_gt_norm
        imu_overlap = vel_imu_norm

    window_len = int(20.0 / dt_resample)
    gt_window = gt_overlap[:window_len]
    imu_window = imu_overlap[:window_len]

    # Step 3: Fine Correlation on the exact 20s overlap
    print("Calculating fine time offset on 20s overlap...")
    correlation_fine = signal.correlate(gt_window, imu_window, mode='full')
    lags_fine = signal.correlation_lags(len(gt_window), len(imu_window), mode='full')
    
    best_lag_fine = lags_fine[np.argmax(correlation_fine)]
    fine_offset_sec = best_lag_fine * dt_resample
    print(f"Fine Time Offset Adjustment: {fine_offset_sec:.3f} seconds")

    # Step 4: Final Offset Calculation
    time_offset_sec = rough_offset_sec + fine_offset_sec 
    print(f"Final Calculated Time Offset: {time_offset_sec:.3f} seconds")

    # ==========================================
    # 5. Shift Timestamps & Merge
    # ==========================================
    print("Merging datasets...")
    
    df_gt_mapped = pd.DataFrame({
        'elapsed_us': ((t_gt_sec - time_offset_sec) * 1e6).astype(int),
        'qx_gt': df_gt['QxToGlobal1'].to_numpy(),
        'qy_gt': df_gt['QyToGlobal1'].to_numpy(),
        'qz_gt': df_gt['QzToGlobal1'].to_numpy(),
        'qw_gt': df_gt['QwToGlobal1'].to_numpy(),
        'roll_gt': gt_angle_x,
        'pitch_gt': gt_angle_y,
        'yaw_gt': gt_angle_z,
        'gx_gt': gx_gt_clean,
        'gy_gt': gy_gt_clean,
        'gz_gt': gz_gt_clean,
        'x_gt': df_gt['QxToGlobal1'].to_numpy(), 
        'y_gt': df_gt['QyToGlobal1'].to_numpy(),
        'z_gt': df_gt['QzToGlobal1'].to_numpy()
        
    })

    df_imu = df_imu.sort_values('elapsed_us')
    df_gt_mapped = df_gt_mapped.sort_values('elapsed_us')

    df_merged = pd.merge_asof(df_imu, df_gt_mapped, on='elapsed_us', direction='nearest', tolerance=50000)

    # ==========================================
    # 6. Save Output
    # ==========================================
    final_cols = [
        'elapsed_us',
        'gx_dmu_aligned', 'gy_dmu_aligned', 'gz_dmu_aligned', 'temp_dmu',
        'gx_spre_aligned', 'gy_spre_aligned', 'gz_spre_aligned', 'temp_spre',
        'gx_bno_aligned', 'gy_bno_aligned', 'gz_bno_aligned', 'temp_bno',
        'qx_gt', 'qy_gt', 'qz_gt', 'qw_gt',
        'roll_gt', 'pitch_gt', 'yaw_gt',
        'gx_gt', 'gy_gt', 'gz_gt',
        'x_gt', 'y_gt', 'z_gt'
    ]
    
    final_cols = [c for c in final_cols if c in df_merged.columns]
    df_output = df_merged[final_cols]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_output.to_csv(output_path, index=False)
    print(f"Saved merged data to: {output_path}")

    # ==========================================
    # 7. Update README
    # ==========================================
    readme_content = f"\n### Data Alignment (GT vs IMU)\n"
    readme_content += f"- **Calculated Offset:** {time_offset_sec:.4f} seconds ({int(time_offset_sec * 1e6)} us)\n"
    readme_content += f"- **Method:** Symmetric Low-Pass Filter ({cutoff_hz}Hz) + Cross-Correlation\n"

    with open(readme_path, "a", encoding='utf-8') as f:
        f.write(readme_content)
        
    # ==========================================
    # 7. Write Integrated CSV (Dead Reckoning)
    # ==========================================
    print("Performing dead reckoning (Trapezoidal Integration)...")
    
    df_gt = df_gt.dropna(subset=['QxToGlobal1', 'QyToGlobal1', 'QzToGlobal1', 'QwToGlobal1']).reset_index(drop=True)

    # Drop rows where GT OR any of the IMU gyro data is missing (NaN)
    critical_cols = [
        'qx_gt', 
        'gx_dmu_aligned', 'gy_dmu_aligned', 'gz_dmu_aligned',
        'gx_spre_aligned', 'gy_spre_aligned', 'gz_spre_aligned',
        'gx_bno_aligned', 'gy_bno_aligned', 'gz_bno_aligned'
    ]
    df_valid = df_output.dropna(subset=critical_cols).reset_index(drop=True)

    if len(df_valid) == 0:
        print("Error: No valid GT or IMU data found after dropping NaNs.")
        return

    t_sec = df_valid['elapsed_us'].to_numpy(dtype=float) / 1e6

    w_dmu = np.deg2rad(df_valid[['gx_dmu_aligned', 'gy_dmu_aligned', 'gz_dmu_aligned']].to_numpy())
    w_spre = np.deg2rad(df_valid[['gx_spre_aligned', 'gy_spre_aligned', 'gz_spre_aligned']].to_numpy())
    w_bno = np.deg2rad(df_valid[['gx_bno_aligned', 'gy_bno_aligned', 'gz_bno_aligned']].to_numpy())

    q_init = df_valid[['qx_gt', 'qy_gt', 'qz_gt', 'qw_gt']].iloc[0].to_numpy()

    N = len(df_valid)
    q_dmu_traj = np.zeros((N, 4))
    q_spre_traj = np.zeros((N, 4))
    q_bno_traj = np.zeros((N, 4))

    q_dmu_traj[0] = q_init
    q_spre_traj[0] = q_init
    q_bno_traj[0] = q_init

    r_dmu = Rotation.from_quat(q_init)
    r_spre = Rotation.from_quat(q_init)
    r_bno = Rotation.from_quat(q_init)

    # Pre-compute dt array
    dt_arr = np.diff(t_sec)[:, np.newaxis]
    dt_arr[(dt_arr > 1.0) | (dt_arr <= 0)] = 1.0 / target_fps

    # Pre-compute all rotation vectors (Vectorized)
    rot_vec_dmu_all = 0.5 * (w_dmu[:-1] + w_dmu[1:]) * dt_arr
    rot_vec_spre_all = 0.5 * (w_spre[:-1] + w_spre[1:]) * dt_arr
    rot_vec_bno_all = 0.5 * (w_bno[:-1] + w_bno[1:]) * dt_arr

    # Create all delta Rotation objects at C-speed
    delta_r_dmu = Rotation.from_rotvec(rot_vec_dmu_all)
    delta_r_spre = Rotation.from_rotvec(rot_vec_spre_all)
    delta_r_bno = Rotation.from_rotvec(rot_vec_bno_all)

    # Simplified Loop
    for i in tqdm(range(1, N), desc="Dead Reckoning Integration", unit="step"):
        r_dmu = r_dmu * delta_r_dmu[i-1]
        r_spre = r_spre * delta_r_spre[i-1]
        r_bno = r_bno * delta_r_bno[i-1]

        q_dmu_traj[i] = r_dmu.as_quat()
        q_spre_traj[i] = r_spre.as_quat()
        q_bno_traj[i] = r_bno.as_quat()

    df_dr = pd.DataFrame({
        'elapsed_us': df_valid['elapsed_us'],
        
        'qx_dmu': q_dmu_traj[:, 0],
        'qy_dmu': q_dmu_traj[:, 1],
        'qz_dmu': q_dmu_traj[:, 2],
        'qw_dmu': q_dmu_traj[:, 3],
        
        'qx_spre': q_spre_traj[:, 0],
        'qy_spre': q_spre_traj[:, 1],
        'qz_spre': q_spre_traj[:, 2],
        'qw_spre': q_spre_traj[:, 3],
        
        'qx_bno': q_bno_traj[:, 0],
        'qy_bno': q_bno_traj[:, 1],
        'qz_bno': q_bno_traj[:, 2],
        'qw_bno': q_bno_traj[:, 3],
        
        'qx_gt': df_valid['qx_gt'],
        'qy_gt': df_valid['qy_gt'],
        'qz_gt': df_valid['qz_gt'],
        'qw_gt': df_valid['qw_gt'],
        
        'x_gt': df_valid['x_gt'], 
        'y_gt': df_valid['y_gt'],
        'z_gt': df_valid['z_gt']
    })

    dr_output_path = os.path.join(exp_dir, "dead_reckoning_quat.csv")
    df_dr.to_csv(dr_output_path, index=False)
    print(f"Saved dead reckoning results to: {dr_output_path}")

if __name__ == "__main__":
    main()