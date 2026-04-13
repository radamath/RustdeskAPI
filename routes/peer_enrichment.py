"""Shared peer enrichment logic for address book and user views."""

import json
from datetime import datetime, timedelta

import rustdesk_db
from models import Heartbeat


def enrich_peers(peers_json_or_list):
    """Take a list of address book peers and return enriched versions
    with local_ip, hostname, platform, online status, etc."""
    if isinstance(peers_json_or_list, str):
        peers = json.loads(peers_json_or_list or "[]")
    else:
        peers = peers_json_or_list

    peer_ids = [p.get("id") if isinstance(p, dict) else p for p in peers]

    hb_map = {}
    if peer_ids:
        for hb in Heartbeat.query.filter(Heartbeat.id.in_(peer_ids)).all():
            hb_map[hb.id] = hb

    rd_map = {}
    for pid in peer_ids:
        try:
            rd = rustdesk_db.get_peer(pid)
            if rd:
                rd_map[pid] = rd
        except Exception:
            pass

    now_naive = datetime.utcnow()
    threshold = now_naive - timedelta(minutes=5)
    enriched = []

    for p in peers:
        pid = p.get("id") if isinstance(p, dict) else p
        entry = dict(p) if isinstance(p, dict) else {"id": pid}

        hb = hb_map.get(pid)
        if hb:
            entry["local_ip"] = hb.local_ip or ""
            entry["ip"] = hb.ip or ""
            entry["hb_hostname"] = hb.hostname or ""
            entry["os_info"] = hb.os_info or ""
            entry["version"] = hb.version or ""
            try:
                ls = hb.last_seen.replace(tzinfo=None) if hb.last_seen and hb.last_seen.tzinfo else hb.last_seen
                entry["online"] = ls >= threshold if ls else False
            except Exception:
                entry["online"] = False
            entry["last_seen"] = hb.last_seen.isoformat() if hb.last_seen else None
        else:
            entry.setdefault("local_ip", "")
            entry.setdefault("ip", "")
            entry["online"] = False
            entry["last_seen"] = None

        rd = rd_map.get(pid)
        if rd:
            info = rd.get("info", {})
            if not entry.get("hostname") and info.get("hostname"):
                entry["hostname"] = info["hostname"]
            if not entry.get("hostname") and entry.get("hb_hostname"):
                entry["hostname"] = entry["hb_hostname"]
            if not entry.get("platform") and info.get("os"):
                entry["platform"] = info["os"]
            rd_ip = rd.get("ip", "")
            if rd_ip and not entry.get("local_ip"):
                entry["local_ip"] = rd_ip
        else:
            if not entry.get("hostname") and entry.get("hb_hostname"):
                entry["hostname"] = entry["hb_hostname"]

        entry.pop("hb_hostname", None)
        entry.setdefault("hostname", "")
        entry.setdefault("platform", "")
        entry.setdefault("local_ip", "")
        enriched.append(entry)

    return enriched
