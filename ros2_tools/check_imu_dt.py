# Required packages:
# pip install mcap mcap-ros2-support tqdm matplotlib numpy

import sys
from datetime import datetime

from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
from mcap_ros2.reader import read_ros2_messages
from mcap.reader import make_reader

if len(sys.argv) < 2:
    print("Usage: python check_imu_dt.py <bagfile_name>")
    sys.exit(1)

bagfile_name = sys.argv[1].rstrip('/')
bag_file = f'{bagfile_name}/{bagfile_name}_0.mcap'

print(f"[INFO] Loading bag: {bag_file}")

# ───────── Identify IMU topics ─────────
# with open(bag_file, "rb") as f:
#     reader = make_reader(f)
#     summary = reader.get_summary()
    
#     schema_names = {schema.id: schema.name for schema in summary.schemas}

#     # Find IMU topics by checking schema name
#     imu_topics = [
#         ch.topic for ch in summary.channels.values()
#         if 'Imu' in ch.message_encoding or 'sensor_msgs/msg/Imu' in schema_names.get(ch.schema_id, '')
#     ]

imu_topics = ['/imu/data', '/sync_board/imu']

if not imu_topics:
    print("[WARN] No IMU topics found in the bag file.")
    exit()

print("[INFO] Found IMU topics:")
for topic in imu_topics:
    print(f"  • {topic}")

# ───────── Analyze each IMU topic ─────────
for imu_topic in imu_topics:
    print(f"\n[INFO] Processing IMU topic: {imu_topic}")
    timestamps = []
    delta_t_values = []

    for msg in tqdm(read_ros2_messages(bag_file, topics=[imu_topic]), desc=f"Reading {imu_topic}"):
        ts = msg.ros_msg.header.stamp.sec + msg.ros_msg.header.stamp.nanosec * 1e-9
        timestamps.append(ts)
        
    print("[DEBUG] First 5 timestamps (s) and human-readable time:")
    for i, ts in enumerate(timestamps[:5]):
        dt = datetime.utcfromtimestamp(ts)
        print(f"  [{i}] {ts:.9f}  ({dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC)")


    if len(timestamps) < 2:
        print("[WARN] Not enough messages for delta t calculation.")
        continue

    for i in range(1, len(timestamps)):
        dt = timestamps[i] - timestamps[i - 1]
        if dt == 0:
            print("[WARN] Zero delta t detected.")
            continue
        delta_t_values.append(dt * 1000)  # ms

    # ───────── Statistics ─────────
    avg_dt = np.mean(delta_t_values)
    std_dt = np.std(delta_t_values)
    max_dt = np.max(delta_t_values)
    count_not_2ms = sum(1 for dt in delta_t_values if not np.isclose(dt, 2.0, atol=0.001))

    print(f"[STAT] Average delta t: {avg_dt:.3f} ms")
    print(f"[STAT] Std deviation  : {std_dt:.3f} ms")
    print(f"[STAT] Max delta t    : {max_dt:.3f} ms")
    print(f"[STAT] Not equal to 2ms: {count_not_2ms} / {len(delta_t_values)}")

    # ───────── Plot ─────────
    plt.figure(figsize=(10, 6))
    plt.scatter(np.arange(len(delta_t_values)), delta_t_values, s=1)
    plt.title(f'Delta t of IMU Header Timestamps\n{imu_topic}')
    plt.xlabel('Sample Index')
    plt.ylabel('Delta t (ms)')
    plt.text(0, (avg_dt + max_dt) / 2, f'Average: {avg_dt:.2f} ± {std_dt:.3f} ms', fontsize=11)
    plt.grid(True)
    plt.tight_layout()
    plt.show()
