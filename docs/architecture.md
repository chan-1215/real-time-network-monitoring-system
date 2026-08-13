# Architecture & Deployment Notes

이 문서는 프로젝트 당시 남아 있는 구성 기록을 기준으로 네트워크 모니터링 시스템을 정리한 문서입니다.

## 1. Servers

### Main / Monitored Server

- Internal/project address: `10.0.2.3`
- Browser/proxy-side address recorded during testing: `192.168.0.65`
- Components: Apache2, `tcpdump`, Python `requests`, `packet_sender.py`

### Monitoring Server

- Address: `192.168.0.122`
- Dashboard: `http://192.168.0.122`
- Elasticsearch: `http://localhost:9200`
- Elasticsearch index: `main_server_packets`
- Components: Flask, Elasticsearch, Gunicorn, Nginx, systemd

---

## 2. Collection Pipeline

프로젝트 기록에는 두 가지 수집 경로가 있습니다.

### Packetbeat pipeline

```text
Network Traffic
  -> Packetbeat
  -> Elasticsearch
  -> Flask
  -> Web Dashboard
```

Packetbeat를 이용해 네트워크 프로토콜/트래픽 정보를 수집하고 Elasticsearch에 저장한 뒤 Flask에서 조회하는 초기·개발 구조입니다.

### tcpdump forwarding pipeline

```text
Main Server
  -> tcpdump
  -> packet_sender.py
  -> POST http://192.168.0.122/api/packet
  -> Flask
  -> Elasticsearch index: main_server_packets
  -> Web Dashboard
```

최종 단계 기록에서는 메인 서버가 `tcpdump`로 캡처한 패킷을 Python 스크립트가 모니터링 서버로 직접 전송하는 구조가 사용되었습니다.

패킷 수집 시 모니터링 서버 자신(`192.168.0.122`)으로 향하는 트래픽과 SSH `port 22`를 제외하여, 모니터링 시스템이 생성하는 통신이 다시 수집되는 현상을 줄이도록 구성했습니다.

---

## 3. Flask API

### Receive packet

```http
POST /api/packet
Content-Type: application/json
```

수신한 패킷은 `main_server_packets` 인덱스에 저장합니다.

### Reset packet data

```http
POST /api/reset
```

테스트/시연 전에 저장된 패킷 데이터를 초기화하기 위해 사용합니다.

### Dashboard data

복원본에서는 Dashboard 자동 갱신을 위해 다음 조회 API를 분리했습니다.

```text
GET /api/packets
GET /api/stats
GET /health
```

이 조회 API들은 당시 Dashboard 요구사항(총 패킷, 트래픽, 위험 이벤트, IP, 로그)을 동일한 구조로 재현하기 위해 정리본에서 추가한 부분입니다.

---

## 4. Dashboard Information

- Total packet count
- Real-time traffic trend
- Danger event count
- Frequently observed / active IP addresses
- Packet detail logs

Dashboard는 2초 주기로 Flask API를 조회해 화면을 갱신하도록 복원했습니다.

---

## 5. Gunicorn + systemd

프로젝트 기록의 Flask 프로젝트 경로:

```text
/home/master/projects/packetwatcher/app.py
```

서비스 파일 위치:

```text
/etc/systemd/system/packetwatcher.service
/etc/systemd/system/packet_sender.service
```

예시 적용:

```bash
sudo cp systemd/packetwatcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now packetwatcher
sudo systemctl status packetwatcher
```

Packet sender:

```bash
sudo cp systemd/packet_sender.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now packet_sender
sudo systemctl status packet_sender
```

---

## 6. Nginx

```bash
sudo cp nginx/packetwatcher.conf /etc/nginx/sites-available/packetwatcher
sudo ln -s /etc/nginx/sites-available/packetwatcher /etc/nginx/sites-enabled/packetwatcher
sudo nginx -t
sudo systemctl restart nginx
```

Nginx가 `:80` 요청을 Gunicorn/Flask의 `127.0.0.1:5000`으로 Reverse Proxy 합니다.

---

## 7. Troubleshooting Commands

```bash
# Elasticsearch
curl http://localhost:9200
curl http://localhost:9200/_cat/indices?v

# Flask/Gunicorn service
sudo systemctl status packetwatcher
journalctl -u packetwatcher -n 100 --no-pager

# packet sender
sudo systemctl status packet_sender
journalctl -u packet_sender -n 100 --no-pager

# Nginx
sudo nginx -t
sudo systemctl status nginx

# Packet capture
sudo tcpdump -nn -i any 'ip and not host 192.168.0.122 and not port 22'
```

---

## 8. Reconstruction Boundary

서버 IP, Elasticsearch 주소/index, `/api/packet`, `/api/reset`, `packet_sender.py`, `tcpdump`, Gunicorn/Nginx/systemd 구성과 Dashboard 항목은 당시 기록에 남아 있는 내용입니다.

반면 현재 저장소의 HTML/CSS 세부 디자인, 조회용 `/api/stats`·`/api/packets` 구현, 위험 이벤트 판별 규칙 등 일부 구현 세부는 원본 파일 전체가 보존되어 있지 않아 프로젝트 목적과 당시 동작을 재현할 수 있도록 정리한 복원 코드입니다.
