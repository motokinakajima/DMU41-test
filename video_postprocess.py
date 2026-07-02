import argparse
import os
import polars as pl
import pyvista as pv
import numpy as np
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Plot merged IMU data from multiple sensors")
    parser.add_argument("experiment_name", type=str, help="Name of the experiment directory inside results/")
    parser.add_argument("--duration", "-d", type=float, default=10.0, help="Duration to load in minutes (default: 10)")
    parser.add_argument("--fps", type=int, default=30, help="Target FPS for downsampling and video (default: 30)")
    args = parser.parse_args()

    exp_dir = os.path.join("results", args.experiment_name)
    
    input_path = os.path.join(exp_dir, "dead_reckoning_quat.csv")

    # --- 1. Polarsを使った高速な読み込みと間引き ---
    print("Loading and downsampling data with Polars...")
    
    # マイクロ秒を計算 (10分 = 600,000,000 us)
    max_us = int(args.duration * 60 * 1_000_000)
    
    # 1000Hz から 目標FPS (例: 30Hz) に間引くためのステップ幅
    # 1000 / 30 ≒ 33行に1行抽出
    step = int(1000 / args.fps) 

    # scan_csv(LazyFrame)を使うことで、2GBのファイル全体をメモリに載せずに処理します
    df = (
        pl.scan_csv(input_path)
        .filter(pl.col("elapsed_us") <= max_us) # 最初の10分間でカット
        .gather_every(step) # 33行ごとに抽出（ダウンサンプリング）
        .select(["x_gt", "y_gt", "z_gt", "qx_gt", "qy_gt", "qz_gt", "qw_gt"])
        .collect() # ここで初めて実際の計算とメモリ確保が走ります
    )

    # --- 2. データの前処理 (NumpyとScipy) ---
    print(f"Data ready. Total frames for animation: {len(df)}")
    
    # 位置データの抽出
    positions = df.select(["x_gt", "y_gt", "z_gt"]).to_numpy()
    
    # クォータニオンの抽出 (Scipyは [x, y, z, w] の順序をデフォルトとします)
    quats = df.select(["qx_gt", "qy_gt", "qz_gt", "qw_gt"]).to_numpy()
    
    # クォータニオンから回転オブジェクトを作成
    rotations = R.from_quat(quats)
    
    # ベースとなるベクトル <1, 0, 0> を全フレーム分用意して回転させる
    base_vectors = np.array([[1.0, 0.0, 0.0]] * len(df))
    directions = rotations.apply(base_vectors)

    # --- 3. PyVistaによる動画生成 ---
    output_mp4 = os.path.join(exp_dir, "drift_animation.mp4")
    print(f"Generating animation: {output_mp4}")

    plotter = pv.Plotter(off_screen=True) # 画面に表示せずバックグラウンドで描画
    plotter.open_movie(output_mp4, framerate=args.fps)

    # 軌跡全体を薄いグレーの線で描画しておく（ドリフトが分かりやすくなります）
    trajectory = pv.lines_from_points(positions)
    plotter.add_mesh(trajectory, color="lightgray", line_width=2, opacity=0.5)

    # カメラの設定 (データ全体の中心を見て、少し引いた位置にカメラを置く)
    plotter.camera.position = (positions[:, 0].mean(), positions[:, 1].mean(), positions[:, 2].max() + 10)
    plotter.camera.focal_point = positions.mean(axis=0)

    # アニメーションループ
    for i in tqdm(range(len(positions)), desc="Rendering frames"):
        pos = positions[i]
        dir_vec = directions[i]

        # 矢印メッシュを作成 (scaleで矢印の長さを調整可能)
        arrow = pv.Arrow(start=pos, direction=dir_vec, scale=0.5)
        
        # name="current_arrow" と指定することで、毎フレーム古い矢印が上書きされアニメーションになります
        plotter.add_mesh(arrow, name="current_arrow", color="red")
        
        # 軌跡を描き足していく表現にしたい場合は、現在のフレームまでの軌跡を描画
        current_traj = pv.lines_from_points(positions[:i+1])
        plotter.add_mesh(current_traj, name="current_trajectory", color="blue", line_width=4)

        plotter.write_frame()

    plotter.close()
    print("Animation successfully saved!")

if __name__ == "__main__":
    main()