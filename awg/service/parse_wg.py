
from datetime import datetime
import json
import os
from typing import Dict

from service.base_model import ActiveClient, PeerData


def save_client_endpoint(username, endpoint):
    os.makedirs("files/connections", exist_ok=True)
    file_path = os.path.join("files", "connections", f"{username}_ip.json")
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    ip_address = endpoint.split(":")[0]

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data[ip_address] = timestamp

    with open(file_path, "w") as f:
        json.dump(data, f)


def parse_wg_show_output(
    wg_output: str, client_key_map: Dict[str, str]
) -> Dict[str, ActiveClient]:
    active_clients: Dict[str, ActiveClient] = {}
    peer = PeerData()

    def save_if_active(peer: PeerData):
        if not peer.public_key or not peer.is_active():
            return
        username = client_key_map.get(peer.public_key)
        if username:
            client = ActiveClient(
                last_time=peer.latest_handshake or "Нет данных",
                transfer=peer.transfer or "Нет данных",
                endpoint=peer.endpoint or "Нет данных",
            )
            save_client_endpoint(username, client.endpoint)
            active_clients[username] = client

    for line in wg_output.splitlines():
        line = line.strip()
        if not line:
            save_if_active(peer)
            peer = PeerData()
            continue
        key_value = line.split(":", 1)
        if len(key_value) != 2:
            continue
        key, value = key_value[0].strip(), key_value[1].strip()
        match key:
            case "peer":
                peer.public_key = value
            case "endpoint":
                peer.endpoint = value
            case "latest handshake":
                peer.latest_handshake = value
            case "transfer":
                peer.transfer = value

    save_if_active(peer)
    return active_clients