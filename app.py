from collections import Counter, defaultdict
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

ELASTICSEARCH_URL = "http://localhost:9200"
INDEX_NAME = "main_server_packets"
es = Elasticsearch(ELASTICSEARCH_URL)


def normalize_packet(payload):
    """Normalize a packet document before indexing."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": payload.get("timestamp") or now,
        "src_ip": payload.get("src_ip", ""),
        "src_port": payload.get("src_port"),
        "dst_ip": payload.get("dst_ip", ""),
        "dst_port": payload.get("dst_port"),
        "protocol": payload.get("protocol", "UNKNOWN"),
        "length": int(payload.get("length") or 0),
        "danger": bool(payload.get("danger", False)),
        "raw": payload.get("raw", ""),
    }


def recent_packets(size=200):
    if not es.indices.exists(index=INDEX_NAME):
        return []

    result = es.search(
        index=INDEX_NAME,
        size=size,
        sort=[{"timestamp": {"order": "desc"}}],
        query={"match_all": {}},
    )
    return [hit["_source"] for hit in result["hits"]["hits"]]


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.post("/api/packet")
def receive_packet():
    payload = request.get_json(silent=True) or {}
    packet = normalize_packet(payload)
    result = es.index(index=INDEX_NAME, document=packet)
    return jsonify({"ok": True, "id": result.get("_id")}), 201


@app.post("/api/reset")
def reset_packets():
    es.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
    return jsonify({"ok": True, "message": "packet index reset"})


@app.get("/api/packets")
def packets_api():
    size = min(max(request.args.get("size", default=100, type=int), 1), 500)
    return jsonify({"packets": recent_packets(size=size)})


@app.get("/api/stats")
def stats_api():
    packets = recent_packets(size=500)
    total = es.count(index=INDEX_NAME)["count"] if es.indices.exists(index=INDEX_NAME) else 0

    danger_events = sum(1 for packet in packets if packet.get("danger"))

    ip_counter = Counter()
    traffic_by_minute = defaultdict(int)
    for packet in packets:
        if packet.get("src_ip"):
            ip_counter[packet["src_ip"]] += 1
        if packet.get("dst_ip"):
            ip_counter[packet["dst_ip"]] += 1

        timestamp = packet.get("timestamp", "")
        minute = timestamp[:16] if len(timestamp) >= 16 else timestamp
        traffic_by_minute[minute] += int(packet.get("length") or 0)

    traffic = [
        {"time": key, "bytes": traffic_by_minute[key]}
        for key in sorted(traffic_by_minute.keys())[-20:]
    ]

    return jsonify({
        "total_packets": total,
        "danger_events": danger_events,
        "top_ips": [{"ip": ip, "count": count} for ip, count in ip_counter.most_common(8)],
        "traffic": traffic,
    })


@app.get("/health")
def health():
    return jsonify({"ok": es.ping(), "elasticsearch": ELASTICSEARCH_URL})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
