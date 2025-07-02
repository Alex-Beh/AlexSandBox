#!/usr/bin/env python3
"""
cook_cam_sync.py – force‑sync three image topics in a ROS 2 bag to 25 Hz.

Usage
-----
python cook_cam_sync.py  in_bag  out_bag  in_storage  out_storage  \
                         /cam_mid/image_raw  /cam_left/image_raw  /cam_right/image_raw
"""

from __future__ import annotations
import sys
from pathlib import Path

import rclpy
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.utilities import get_message

from rosbag2_py import (
    SequentialReader, SequentialWriter,
    StorageOptions, ConverterOptions,
    TopicMetadata,
)

RATE_HZ   = 25.0
PERIOD_NS = int(1e9 / RATE_HZ)                     # 40 000 000 ns


# ───────── helper functions ────────────────────────────────────────────────
def build_reader(uri: str, storage_id: str) -> SequentialReader:
    ro = StorageOptions(uri=uri, storage_id=storage_id)
    conv = ConverterOptions(input_serialization_format='cdr',
                            output_serialization_format='cdr')
    reader = SequentialReader()
    reader.open(ro, conv)
    return reader


def build_writer(uri: str, storage_id: str,
                 metadata: list[TopicMetadata]) -> SequentialWriter:
    wo = StorageOptions(uri=uri, storage_id=storage_id)
    conv = ConverterOptions('cdr', 'cdr')
    writer = SequentialWriter()
    writer.open(wo, conv)
    for md in metadata:
        writer.create_topic(md)
    return writer


def gather_header_stamps(uri: str, storage_id: str,
                         topic_name: str,
                         msg_cls: type) -> list[int]:
    """Return every header.stamp (nanoseconds) for one topic."""
    reader = build_reader(uri, storage_id)
    stamps: list[int] = []
    while reader.has_next():
        topic, data, _ts = reader.read_next()
        if topic != topic_name:
            continue
        msg = deserialize_message(data, msg_cls)
        stamps.append(msg.header.stamp.sec * 1_000_000_000 +
                      msg.header.stamp.nanosec)
    return stamps


def find_common_anchor(lists: list[list[int]]) -> int:
    """Earliest timestamp that appears in **all** lists."""
    common = set(lists[0])
    for lst in lists[1:]:
        common &= set(lst)
    if not common:
        raise RuntimeError("No timestamp present on all three camera topics.")
    return min(common)


# ─────────────────────────────── main ─────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 8:
        sys.exit(__doc__)

    in_uri, out_uri, in_storage, out_storage, t1, t2, t3 = sys.argv[1:]
    CAM_TOPICS = [t1, t2, t3]
    IMU_TOPIC = '/imu/data'

    rclpy.init(args=None)

    # 1. Open a reader once to fetch metadata and build a msg‑class lookup.
    reader_meta = build_reader(in_uri, in_storage)
    topic_meta  = reader_meta.get_all_topics_and_types()          # list[TopicMetadata]
    MSG_CLASS   = {m.name: get_message(m.type) for m in topic_meta}

    # 2.1 First pass – collect header.stamp lists & choose anchor.
    stamp_lists = [
        gather_header_stamps(in_uri, in_storage, topic, MSG_CLASS[topic])
        for topic in CAM_TOPICS
    ]
    anchor_ns = find_common_anchor(stamp_lists)
    first_idx = {
        topic: stamp_lists[i].index(anchor_ns)
        for i, topic in enumerate(CAM_TOPICS)
    }

    print(f"Anchor ts : {anchor_ns} ns  ({anchor_ns/1e9:.6f} s)")
    print(f"First idx : {first_idx}")
    '''
    Anchor ts : 1750838478817840000 ns  (1750838478.817840 s)
    First idx : {'/middle_camera_node/image_raw': 0, '/left_camera_node/image_raw': 1, '/right_camera_node/image_raw': 0}
    '''

    # Step 2.2 — Find first IMU message timestamp
    imu_reader = build_reader(in_uri, in_storage)
    imu_start_time_ns = None
    while imu_reader.has_next():
        topic, data, _ts = imu_reader.read_next()
        if topic == IMU_TOPIC:
            imu_msg = deserialize_message(data, MSG_CLASS[topic])
            imu_start_time_ns = imu_msg.header.stamp.sec * 1_000_000_000 + imu_msg.header.stamp.nanosec
            break

    if imu_start_time_ns is None:
        sys.exit(f"[ERROR] No IMU messages found on topic {IMU_TOPIC}")

    imu_offset_ns = anchor_ns - imu_start_time_ns
    print(f"[INFO] IMU time offset: {imu_offset_ns} ns ({imu_offset_ns / 1e9:.6f} s)")
    print(f"[DEBUG] First IMU ts: {imu_start_time_ns} ns ({imu_start_time_ns / 1e9:.6f} s)")

    # 2. Open reader/writer, prepare tracking
    reader = build_reader(in_uri, in_storage)
    writer = build_writer(out_uri, out_storage, topic_meta)
    last_written_ts: dict[str, int] = {}

    # 3. Iterate and write only unique timestamped camera messages
    while reader.has_next():
        topic, data, ts = reader.read_next()

        if topic == IMU_TOPIC:
            imu_msg = deserialize_message(data, MSG_CLASS[topic])
            imu_ts_ns = imu_msg.header.stamp.sec * 1_000_000_000 + imu_msg.header.stamp.nanosec
            new_imu_ts = imu_ts_ns + imu_offset_ns

            imu_msg.header.stamp.sec = new_imu_ts // 1_000_000_000
            imu_msg.header.stamp.nanosec = new_imu_ts % 1_000_000_000

            data = serialize_message(imu_msg)
            writer.write(topic, data, new_imu_ts)
            continue

        if topic not in CAM_TOPICS:
            writer.write(topic, data, ts)
            continue

        msg = deserialize_message(data, MSG_CLASS[topic])
        msg_ts = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec

        # Skip duplicate header.stamp for same topic
        if topic in last_written_ts and msg_ts == last_written_ts[topic]:
            print(f"⚠ Skipping duplicate timestamp on topic {topic} at {msg_ts}")
            continue

        writer.write(topic, data, msg_ts)
        last_written_ts[topic] = msg_ts

    print(f"✔  Cooked bag written → {out_uri}")
    rclpy.shutdown()

