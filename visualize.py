#!/usr/bin/env python3
import argparse
import csv
import glob
from pathlib import Path

import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go


METRICS = [
    ("roll", "Roll [deg], 1回積分"),
    ("pitch", "Pitch [deg], 1回積分"),
    ("yaw", "Yaw [deg], 1回積分"),
    ("x", "X [m], 2回積分"),
    ("y", "Y [m], 2回積分"),
    ("z", "Z [m], 2回積分"),
]


def load_csv(path):
    timestamps = []
    series = {name: [] for name, _ in METRICS}

    with Path(path).open("r", newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        for row_index, row in enumerate(reader):
            timestamp_text = row.get("timestamp", "")
            timestamps.append(float(timestamp_text) if timestamp_text else float(row_index))
            for name, _ in METRICS:
                series[name].append(float(row[name]))

    data = {name: np.asarray(values, dtype=float) for name, values in series.items()}
    data["timestamp"] = np.asarray(timestamps, dtype=float)
    return data


def choose_indices(length, max_points):
    if length <= max_points:
        return np.arange(length)
    return np.unique(np.linspace(0, length - 1, max_points, dtype=int))


def resolve_files(file_args):
    if file_args:
        return [str(Path(path)) for path in file_args]

    return sorted(glob.glob("trial*.csv"))


def plot_trials(files, output_path=None, max_points=2000, show=False):
    if not files:
        raise FileNotFoundError("No CSV files found. Pass files explicitly or create trial*.csv files.")

    loaded = [(Path(path).stem, load_csv(path)) for path in files]
    common_length = min(len(data["timestamp"]) for _, data in loaded)
    indices = choose_indices(common_length, max_points)

    # ==============================================================
    # 統計アップデート：各試行のバイアスを蓄積してガウス分布処理
    # ==============================================================
    print("\n=== 各トライアルの個別推定結果 ===")
    bias_summary = {name: [] for name, _ in METRICS}
    
    for trial_label, data in loaded:
        print(f"【 {trial_label} 】")
        timestamps = data["timestamp"]
        
        if len(timestamps) < 2:
            print("  データが少なすぎて計算できません。")
            continue

        for metric_name, _ in METRICS:
            values = data[metric_name]
            
            if metric_name in ["roll", "pitch", "yaw"]:
                # 1回積分の傾き（ジャイロバイアス）
                slope, _ = np.polyfit(timestamps, values, 1)
                bias_summary[metric_name].append(slope)
                print(f"  {metric_name.upper():<5} (Gyro)  : {slope:+.8f} deg/s")
            else:
                # 2回積分から逆算した加速度バイアス
                coefs = np.polyfit(timestamps, values, 2)
                accel_bias = coefs[0] * 2
                bias_summary[metric_name].append(accel_bias)
                print(f"  {metric_name.upper():<5} (Accel) : {accel_bias:+.8f} m/s^2")

    print("\n" + "="*60)
    print(" === 全トライアル統合統計 (ガウス分布アプローチ) ===")
    print("="*60)
    print("複数回の試行から、ノイズが正規分布に従うと仮定して真の値を推定しました。")
    print("アプリに入力するキャリブレーション値には、この「平均値 (Mean)」の符号を反転させた値を使ってください。\n")
    
    for metric_name, _ in METRICS:
        biases = bias_summary[metric_name]
        if not biases:
            continue
        
        # 平均(μ)と不偏標準偏差(σ)の計算
        mean_bias = np.mean(biases)
        std_bias = np.std(biases, ddof=1) if len(biases) > 1 else 0.0
        
        unit = "deg/s" if metric_name in ["roll", "pitch", "yaw"] else "m/s^2"
        sensor_type = "Gyro " if metric_name in ["roll", "pitch", "yaw"] else "Accel"
        
        print(f"【 {metric_name.upper()} ({sensor_type}) 】")
        print(f"  平均値 (Mean μ)      : {mean_bias:+.8f} {unit}")
        print(f"  標準偏差 (Std Dev σ) : {std_bias:.8f} {unit}")
        if len(biases) > 1:
            # 統計的に、約68.3%の確率でバイアスはこの範囲に収まる（±1σ区間）
            print(f"  信頼区間 (μ ± 1σ)   : [{mean_bias - std_bias:+.8f} 〜 {mean_bias + std_bias:+.8f}] {unit}")
        else:
            print("  (※データが1件のみのため、標準偏差は算出できません)")
        print("-" * 50)
    print("============================================================\n")
    # ==============================================================

    fig = make_subplots(
        rows=3,
        cols=2,
        shared_xaxes=True,
        subplot_titles=[name for name, _ in METRICS],
        horizontal_spacing=0.08,
        vertical_spacing=0.1,
    )

    for metric_index, (metric_name, metric_title) in enumerate(METRICS, start=1):
        row = (metric_index - 1) // 2 + 1
        col = (metric_index - 1) % 2 + 1
        for trial_label, data in loaded:
            timestamps = data["timestamp"][:common_length][indices]
            values = data[metric_name][:common_length][indices]
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    mode="lines",
                    name=trial_label,
                    showlegend=(metric_index == 1),
                    line=dict(width=1.5),
                ),
                row=row,
                col=col,
            )
        fig.update_yaxes(title_text=metric_title, row=row, col=col)
        fig.update_xaxes(title_text="timestamp [s]", row=row, col=col)

    fig.update_layout(
        title="DMU41 Trials",
        height=1100,
        width=1400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=100, b=40),
    )

    if output_path is None:
        output_path = "visualize.html"

    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"saved: {output_path}")

    if show:
        fig.show()


def main():
    parser = argparse.ArgumentParser(description="Visualize DMU41 trial CSV files")
    parser.add_argument("files", nargs="*", help="CSV files to plot. Defaults to trial*.csv")
    parser.add_argument("--output", default="visualize.html", help="Output HTML path")
    parser.add_argument("--show", action="store_true", help="Also open an interactive window or browser tab")
    parser.add_argument("--max-points", type=int, default=2000, help="Maximum plotted points per trial")
    args = parser.parse_args()

    files = resolve_files(args.files)
    plot_trials(files, output_path=args.output, max_points=args.max_points, show=args.show)


if __name__ == "__main__":
    main()