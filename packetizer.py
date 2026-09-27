#!/usr/bin/env python3
import json
import os
import time
import argparse

CHUNK_SIZE = 128  # Payload chunk size in bytes for files

def send_chat(text, dest_addr, tx_file):
    """ High Priority (Priority 1) Chat Message """
    packet = {
        "priority": 1,
        "type": "DATA",
        "dest": dest_addr,
        "seq": int(time.time() * 1000) % 100000,
        "payload_type": "text",
        "payload": text
    }
    write_to_tx_file(packet, tx_file)
    print(f"[TX Chat] Sent (Priority 1): {text}")

def send_file(file_path, dest_addr, tx_file):
    """ Low Priority (Priority 2) File Transfer Chunking """
    if not os.path.exists(file_path):
        print(f"[Error] File not found: {file_path}")
        return

    file_name = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        data = f.read()

    total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    file_id = int(time.time()) % 10000

    print(f"[TX File] Split '{file_name}' into {total_chunks} chunks (Priority 2)...")

    packets = []
    for i in range(total_chunks):
        chunk = data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE].hex()  # Hex encode binary
        packet = {
            "priority": 2,
            "type": "DATA",
            "dest": dest_addr,
            "seq": (file_id * 100) + i,
            "file_name": file_name,
            "chunk_idx": i,
            "total_chunks": total_chunks,
            "payload_type": "file_chunk",
            "payload": chunk
        }
        packets.append(packet)

    write_to_tx_file(packets, tx_file)
    print(f"[TX File] Queued {total_chunks} chunks to {tx_file}.")

def write_to_tx_file(packets, tx_file):
    existing = []
    if os.path.exists(tx_file):
        try:
            with open(tx_file, 'r') as f:
                content = f.read().strip()
                if content:
                    existing = json.loads(content)
                    if not isinstance(existing, list):
                        existing = [existing]
        except Exception:
            existing = []

    if isinstance(packets, list):
        existing.extend(packets)
    else:
        existing.append(packets)

    with open(tx_file, 'w') as f:
        json.dump(existing, f, indent=2)

def read_rx_file(rx_file):
    """ Polls and prints incoming decoded messages """
    if not os.path.exists(rx_file):
        return
    try:
        with open(rx_file, 'r') as f:
            content = f.read().strip()
            if content:
                packets = json.loads(content)
                print("\n--- [INCOMING MESSAGES] ---")
                for pkt in packets:
                    p_type = pkt.get("payload_type", "unknown")
                    src = pkt.get("src", "Unknown")
                    if p_type == "text":
                        print(f" From {src}: {pkt.get('payload')}")
                    elif p_type == "file_chunk":
                        print(f" File Chunk [{pkt.get('chunk_idx')+1}/{pkt.get('total_chunks')}] of '{pkt.get('file_name')}'")
                print("---------------------------\n")
    except Exception as e:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SDR Transceiver Packetizer CLI")
    parser.add_argument("--node", choices=["A", "B"], required=True, help="Node Identity (A or B)")
    args = parser.parse_args()

    tx_file = f"/tmp/node{args.node}_tx.json"
    rx_file = f"/tmp/node{args.node}_rx.json"
    target_dest = "B1" if args.node == "A" else "A1"

    print(f"=== SDR Transceiver Terminal (Node {args.node}) ===")
    print(f"Writing to: {tx_file} | Destination: {target_dest}")
    print("Commands:")
    print("  msg <text>       - Send High Priority Chat Message")
    print("  file <filepath>  - Send Low Priority File")
    print("  rx               - Read Incoming Received Messages")
    print("  exit             - Quit Terminal\n")

    while True:
        try:
            cmd = input(f"Node-{args.node}> ").strip()
            if not cmd:
                continue
            if cmd.startswith("msg "):
                send_chat(cmd[4:], target_dest, tx_file)
            elif cmd.startswith("file "):
                send_file(cmd[5:], target_dest, tx_file)
            elif cmd == "rx":
                read_rx_file(rx_file)
            elif cmd == "exit":
                break
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            break