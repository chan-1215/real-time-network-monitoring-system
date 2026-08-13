import re
import subprocess
from datetime import datetime, timezone

import requests

MONITORING_API = "http://192.168.0.122/api/packet"
MONITORING_HOST = "192.168.0.122"
INTERFACE = "any"

ENDPOINT_RE = r"(\d{1,3}(?:\.\d{1,3}){3})(?:\.(\d+))?"
PACKET_RE = re.compile(
    rf"IP\s+{ENDPOINT_RE}\s+>\s+{ENDPOINT_RE}:.*?(?:length\s+(\d+))?$"
)


def parse_tcpdump_line(line):
    """Parse the IPv4 endpoints from a tcpdump text line."""
    match = PACKET_RE.search(line.strip())
    if not match:
        return None

    src_ip, src_port, dst_ip, dst_port, length = match.groups()
    raw_lower = line.lower()

    protocol = "TCP"
    if "icmp" in raw_lower:
        protocol = "ICMP"
    elif "udp" in raw_lower:
        protocol = "UDP"

    # Reconstructed portfolio rule for highlighting events on commonly abused ports.
    suspicious_ports = {23, 445, 3389}
    ports = {int(p) for p in (src_port, dst_port) if p and p.isdigit()}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "src_ip": src_ip,
        "src_port": int(src_port) if src_port else None,
        "dst_ip": dst_ip,
        "dst_port": int(dst_port) if dst_port else None,
        "protocol": protocol,
        "length": int(length) if length else 0,
        "danger": bool(ports & suspicious_ports),
        "raw": line.strip(),
    }


def send_packet(packet):
    response = requests.post(MONITORING_API, json=packet, timeout=3)
    response.raise_for_status()


def capture_packets():
    command = [
        "tcpdump",
        "-nn",
        "-l",
        "-i",
        INTERFACE,
        "ip",
        "and",
        "not",
        "host",
        MONITORING_HOST,
        "and",
        "not",
        "port",
        "22",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    if process.stdout is None:
        raise RuntimeError("tcpdump stdout is unavailable")

    for line in process.stdout:
        packet = parse_tcpdump_line(line)
        if not packet:
            continue

        try:
            send_packet(packet)
            print(f"[sent] {packet['src_ip']} -> {packet['dst_ip']}")
        except requests.RequestException as exc:
            print(f"[send failed] {exc}")


if __name__ == "__main__":
    capture_packets()
