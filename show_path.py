# show_path.py
# Reads /tmp/path_trace.log and prints a clean hop-by-hop path trace

import json
import sys

LOG_FILE = "/tmp/path_trace.log"

def load_logs():
    entries = []
    try:
        with open(LOG_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except FileNotFoundError:
        print("[!] No log file found. Run the topology and generate traffic first.")
        sys.exit(1)
    return entries

def display_path(src_ip=None, dst_ip=None):
    entries = load_logs()
    filtered = entries
    if src_ip:
        filtered = [e for e in filtered if e.get('src_ip') == src_ip]
    if dst_ip:
        filtered = [f for f in filtered if f.get('dst_ip') == dst_ip]

    if not filtered:
        print(f"[!] No path found for {src_ip} → {dst_ip}")
        return

    print(f"\n{'='*60}")
    print(f"  PATH TRACE: {src_ip} → {dst_ip}")
    print(f"{'='*60}")
    for i, e in enumerate(filtered, 1):
        print(f"\n  Hop {i}: Switch dpid={e['switch']}")
        print(f"    Timestamp : {e['timestamp']}")
        print(f"    Src MAC   : {e['src_mac']}  →  Dst MAC: {e['dst_mac']}")
        print(f"    Src IP    : {e['src_ip']}    →  Dst IP: {e['dst_ip']}")
        print(f"    In Port   : {e['in_port']}   →  Out Port: {e['out_port']}")
        print(f"    Protocol  : {e['protocol']}")
    print(f"\n{'='*60}")
    print(f"  Total hops logged: {len(filtered)}")
    print(f"{'='*60}\n")

def display_all():
    entries = load_logs()
    print(f"\n{'='*60}")
    print(f"  ALL LOGGED FLOWS ({len(entries)} entries)")
    print(f"{'='*60}")
    flows_seen = {}
    for e in entries:
        key = (e.get('src_ip'), e.get('dst_ip'), e.get('switch'))
        if key not in flows_seen:
            flows_seen[key] = e
            print(f"  SW={e['switch']} | {e.get('src_ip','?')} → {e.get('dst_ip','?')} "
                  f"| in={e['in_port']} out={e['out_port']} | {e['protocol']}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    if len(sys.argv) == 3:
        display_path(sys.argv[1], sys.argv[2])
    else:
        display_all()
