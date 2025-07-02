#!/usr/bin/env python3
"""
plot_kalibr.py  –  visualise camera↔IMU extrinsics from a Kalibr‑style YAML file.

Usage
-----
python plot_kalibr.py  path/to/camchain.yaml
"""
import sys
import yaml
import numpy as np
import matplotlib.pyplot as plt


def load_camchain(yaml_path: str) -> dict:
    """Read the YAML file and return a dict of {name: 4×4 T_cam_imu}."""
    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)
    T = {"IMU": np.eye(4)}
    for name, cfg in raw.items():
        print(name, cfg)
        T[name] = np.array(cfg["T_cam_imu"])
    return T


def plot_frame(ax, T, label, length=0.05):
    o = T[:3, 3]
    x, y, z = T[:3, 0] * length, T[:3, 1] * length, T[:3, 2] * length
    ax.quiver(*o, *x, color="r", arrow_length_ratio=0.2)
    ax.quiver(*o, *y, color="g", arrow_length_ratio=0.2)
    ax.quiver(*o, *z, color="b", arrow_length_ratio=0.2)
    ax.text(*o, f" {label}", fontsize=9)


def main(argv):
    if len(argv) != 2:
        print(f"Usage: {argv[0]} calib.yaml")
        sys.exit(1)

    transforms = load_camchain(argv[1])

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    for lbl, T in transforms.items():
        plot_frame(ax, T, lbl)

    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
    ax.set_title("Camera–IMU rig")

    # nice bounding box
    pts = np.vstack([T[:3, 3] for T in transforms.values()])
    rng = (pts.max(0) - pts.min(0)).max() / 2
    mid = pts.mean(0)
    ax.set_xlim(mid[0]-rng, mid[0]+rng)
    ax.set_ylim(mid[1]-rng, mid[1]+rng)
    ax.set_zlim(mid[2]-rng, mid[2]+rng)

    plt.show()


if __name__ == "__main__":
    main(sys.argv)
