#!/usr/bin/env python3
"""
Compare the timestamp stream of a *reference* image topic against
one or more *target* image topics inside a single MCAP bag.

Example
-------
python check_cam_sync.py bag.mcap \
        --reference /cam_left/image_raw \
        --targets   /cam_middle/image_raw /cam_right/image_raw \
        --tolerance_ns 0
        
python check_cam_sync.py rosbag2_2025-05-15-14-28-15/ --reference /cam1/image_raw --targets /cam2/image_raw --tolerance_ns 0
python check_cam_sync.py rosbag2_2025-06-25-10-55-31/ --reference /middle_camera_node/image_raw --targets /left_camera_node/image_raw /right_camera_node/image_raw --tolerance_ns 10


"""
from pathlib import Path
from rosbags.highlevel import AnyReader
import argparse

# ---------- CLI --------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(
        description="Check timestamp sync in an MCAP bag")
    p.add_argument("bag_path",
                   help="Path to a .mcap file (single-file bag)")
    p.add_argument("--reference", required=True,
                   help="Reference image topic (e.g. left camera)")
    p.add_argument("--targets", required=True, nargs='+',
                   help="One or more target image topics to compare")
    p.add_argument("--tolerance_ns", type=int, default=0,
                   help="Max allowed time difference (nanoseconds)")
    return p.parse_args()

# ---------- helpers ----------------------------------------------------------
def sanitize_topic(topic: str) -> str:
    return topic.strip("/").replace("/", "_")


def extract_timestamps(path: str, topic: str) -> list[tuple[int, int]]:
    """Return a list[(sec, nsec)] of header.stamp for *topic* in *path*."""
    ts: list[tuple[int, int]] = []
    with AnyReader([Path(path)]) as reader:
        conns = [c for c in reader.connections if c.topic == topic]
        for conn, _, raw in reader.messages(connections=conns):
            msg = reader.deserialize(raw, conn.msgtype)
            ts.append((msg.header.stamp.sec, msg.header.stamp.nanosec))
    return ts


def diff_ns(a: tuple[int, int], b: tuple[int, int]) -> int:
    """|a-b| in nanoseconds, where each ts = (sec, nsec)."""
    sec = a[0] - b[0]
    nsec = a[1] - b[1]
    if nsec < 0:
        sec -= 1
        nsec += 1_000_000_000
    return abs(sec * 1_000_000_000 + nsec)


def find_closest_forward(t_ref, ts_target, start_idx):
    best_i, best_d = -1, float("inf")
    for i in range(start_idx, len(ts_target)):
        d = diff_ns(t_ref, ts_target[i])
        if d < best_d:
            best_i, best_d = i, d
        else:                       # list is time-ordered; diff starts growing
            break
    return best_i, best_d


def check_duplicates(timestamps, label):
    seen = {}  # map from timestamp -> first index
    duplicates = 0
    for i, ts in enumerate(timestamps):
        if ts in seen:
            first_i = seen[ts]
            print(f"!!! Duplicate timestamp in {label} at index {i} (same as index {first_i}): "
                  f"{ts[0]}.{str(ts[1]).zfill(9)}")
            duplicates += 1
        else:
            seen[ts] = i
    if duplicates == 0:
        print(f"--- No duplicate timestamps found in {label}")


def check_pair(reference_ts, target_ts, tol_ns):
    """
    Print only the unsynchronised pairs:
      ref_idx, tgt_idx, Δ(ns),   ref_time(sec.ns),   tgt_time(sec.ns)
    """
    i_target = 0
    unsynced = 0

    for i_ref, t_ref in enumerate(reference_ts):
        idx, d = find_closest_forward(t_ref, target_ts, i_target)
        if idx == -1:
            break
        i_target = idx + 1

        if d > tol_ns:
            unsynced += 1
            ref_time = f"{t_ref[0]}.{str(t_ref[1]).zfill(9)}"
            tgt_time = f"{target_ts[idx][0]}.{str(target_ts[idx][1]).zfill(9)}"
            print(f"!!! ref[{i_ref}] vs tgt[{idx}]  Δ={d/1e6:.3f} ms  "
                  f"ref={ref_time}  tgt={tgt_time}")

    total = min(len(reference_ts), len(target_ts))
    print(
        f"\nChecked {total} pairs — {unsynced} exceeded tolerance ({tol_ns} ns)\n")


# ---------- main -------------------------------------------------------------
def main():
    args = parse_args()
    print(f"\nBag      : {args.bag_path}")
    print(f"Reference: {args.reference}")
    print(f"Targets  : {', '.join(args.targets)}")
    print(f"Tolerance: {args.tolerance_ns} ns\n")

    ref_ts = extract_timestamps(args.bag_path, args.reference)
    if not ref_ts:
        raise RuntimeError(
            f"No messages on reference topic '{args.reference}'")

    print("--- Checking reference ---")
    check_duplicates(ref_ts, args.reference)  # <-- check ref duplicates
    print("\n")

    for tgt in args.targets:
        print(f"--- Checking {tgt} ---")
        tgt_ts = extract_timestamps(args.bag_path, tgt)
        if not tgt_ts:
            print(f"✗ No messages found – skipping\n")
            continue
        check_duplicates(tgt_ts, tgt)         # <-- check target duplicates
        # check_pair(ref_ts, tgt_ts, args.tolerance_ns)
        print("\n")


if __name__ == "__main__":
    main()
