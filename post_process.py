import argparse
import os
import pandas as pd
from tqdm import tqdm
from parser import SimplifiedDMU41Parser

def main():
    parser = argparse.ArgumentParser(description="Post-processing IMU data from multiple sensors")
    parser.add_argument("experiment_name", type=str, help="Name of the experiment directory inside results/")
    args = parser.parse_args()

    exp_dir = os.path.join("results", args.experiment_name)
    bno_path = os.path.join(exp_dir, "bno.csv")
    spresense_path = os.path.join(exp_dir, "spresense.csv")
    dmu_path = os.path.join(exp_dir, "dmu.bin")
    output_path = os.path.join(exp_dir, "postprocessing.csv")

    pbar = tqdm(total=5, desc="Processing IMU Data")

    # ==========================================
    # 1. DMU Binary Parser (Placeholder)
    # ==========================================
    # TODO: Implement your custom DMU binary parser here
    # The output df_dmu must contain 'elapsed_sec' and data columns.
    # df_dmu = parse_dmu(dmu_path)
    
    # Temporary empty DataFrame for compilation/testing fallback
    df_dmu = pd.DataFrame(columns=['elapsed_sec', 'gx_dmu', 'gy_dmu', 'gz_dmu', 'ax_dmu', 'ay_dmu', 'az_dmu', 'temp_dmu'])
    pbar.update(1)

    # ==========================================
    # 2. Process Spresense Data
    # ==========================================
    if os.path.exists(spresense_path):
        df_spre = pd.read_csv(spresense_path)
        df_spre = df_spre.iloc[1:].reset_index(drop=True)
        
        df_spre['micros_diff'] = df_spre['micros'].diff()
        df_spre.loc[df_spre['micros_diff'] < 0, 'micros_diff'] += 4294967296
        df_spre['micros_diff'] = df_spre['micros_diff'].fillna(0)
        df_spre['elapsed_sec'] = df_spre['micros_diff'].cumsum() / 1000000.0
        
        df_spre = df_spre.rename(columns={  # type: ignore
            'gx': 'gx_spre', 'gy': 'gy_spre', 'gz': 'gz_spre',
            'ax': 'ax_spre', 'ay': 'ay_spre', 'az': 'az_spre',
            'temp': 'temp_spre'
        })
        df_spre = df_spre[['elapsed_sec', 'gx_spre', 'gy_spre', 'gz_spre', 'ax_spre', 'ay_spre', 'az_spre', 'temp_spre']]
    else:
        df_spre = pd.DataFrame(columns=['elapsed_sec'])
    pbar.update(1)

    # ==========================================
    # 3. Process BNO Data
    # ==========================================
    if os.path.exists(bno_path):
        df_bno = pd.read_csv(bno_path)
        df_bno = df_bno.iloc[1:].reset_index(drop=True)
        
        df_bno['micros_diff'] = df_bno['micros'].diff()
        df_bno.loc[df_bno['micros_diff'] < 0, 'micros_diff'] += 4294967296
        df_bno['micros_diff'] = df_bno['micros_diff'].fillna(0)
        df_bno['elapsed_sec'] = df_bno['micros_diff'].cumsum() / 1000000.0
        
        df_bno = df_bno.rename(columns={ # type: ignore
            'gx': 'gx_bno', 'gy': 'gy_bno', 'gz': 'gz_bno',
            'ax': 'ax_bno', 'ay': 'ay_bno', 'az': 'az_bno',
            'temp': 'temp_bno'
        })
        df_bno = df_bno[['elapsed_sec', 'gx_bno', 'gy_bno', 'gz_bno', 'ax_bno', 'ay_bno', 'az_bno', 'temp_bno']]
    else:
        df_bno = pd.DataFrame(columns=['elapsed_sec'])
    pbar.update(1)

    # ==========================================
    # 4. Coordinate Transformation (Placeholder)
    # ==========================================
    # TODO: Implement your rotation matrix multiplication here
    # Example:
    # import numpy as np
    # R_bno = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    # df_bno[['gx_bno', 'gy_bno', 'gz_bno']] = df_bno[['gx_bno', 'gy_bno', 'gz_bno']].dot(R_bno.T)
    # df_bno[['ax_bno', 'ay_bno', 'az_bno']] = df_bno[['ax_bno', 'ay_bno', 'az_bno']].dot(R_bno.T)
    pbar.update(1)

    # ==========================================
    # 5. Merge Dataframes using merge_asof
    # ==========================================
    # Use DMU (1000Hz) as base if available, otherwise fallback to Spresense
    if not df_dmu.empty and df_dmu['elapsed_sec'].notna().any():
        df_dmu = df_dmu.sort_values('elapsed_sec')
        if not df_spre.empty:
            df_spre = df_spre.sort_values('elapsed_sec')
            df_merged = pd.merge_asof(df_dmu, df_spre, on='elapsed_sec', direction='nearest', tolerance=0.01)
        else:
            df_merged = df_dmu
            
        if not df_bno.empty:
            df_bno = df_bno.sort_values('elapsed_sec')
            df_merged = pd.merge_asof(df_merged, df_bno, on='elapsed_sec', direction='nearest', tolerance=0.05)
    else:
        if not df_spre.empty:
            df_spre = df_spre.sort_values('elapsed_sec')
            if not df_bno.empty:
                df_bno = df_bno.sort_values('elapsed_sec')
                df_merged = pd.merge_asof(df_spre, df_bno, on='elapsed_sec', direction='nearest', tolerance=0.05)
            else:
                df_merged = df_spre
        else:
            df_merged = df_bno

    # Select final columns (9 gyro elements + temperatures)
    final_cols = ['elapsed_sec']
    if 'gx_dmu' in df_merged.columns: final_cols.extend(['gx_dmu', 'gy_dmu', 'gz_dmu', 'temp_dmu'])
    if 'gx_spre' in df_merged.columns: final_cols.extend(['gx_spre', 'gy_spre', 'gz_spre', 'temp_spre'])
    if 'gx_bno' in df_merged.columns: final_cols.extend(['gx_bno', 'gy_bno', 'gz_bno', 'temp_bno'])
    
    final_cols = [c for c in final_cols if c in df_merged.columns]
    df_output = df_merged[final_cols]

    # Save to CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_output.to_csv(output_path, index=False)
    pbar.update(1)
    pbar.close()

    print(f"Successfully processed and saved to {output_path}")

if __name__ == "__main__":
    main()