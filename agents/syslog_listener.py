"""
UDP/TCP Syslog Listener — port 514
Receives raw syslog from firewalls, routers, Linux servers.
Maps source IP → tenant via MongoDB, then enqueues to Redis stream.
"""
from __future__ import annotations

import asyncio
import re
import logging
from datetime import datetime, timezone

from db.mongo import connect_mongo, get_collection
from db.redis_client import connect_redis, xadd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [syslog] %(message)s")
log = logging.getLogger(__name__)

UDP_PORT = 514
TCP_PORT = 601  # RFC 3195 reliable syslog

# Cache: ip → tenant_id  (refreshed every 60s)
_ip_cache: dict[str, str] = {}
_cache_ts: float = 0.0
CACHE_TTL = 60.0


async def _refresh_cache():
    global _ip_cache, _cache_ts
    now = asyncio.get_event_loop().time()
    if now - _cache_ts < CACHE_TTL:
        return
    col = get_collection("source_ips")
    docs = col.find({}, {"ip": 1, "tenant_id": 1})
    mapping = {}
    async for doc in docs:
        mapping[doc["ip"]] = doc["tenant_id"]
    _ip_cache = mapping
    _cache_ts = now
    log.info("IP cache refreshed: %d registered sources", len(mapping))


async def _lookup_tenant(ip: str) -> str | None:
    await _refresh_cache()
    return _ip_cache.get(ip)


def _parse_syslog(data: bytes) -> str:
    """Return the human-readable part of a syslog message."""
    try:
        msg = data.decode("utf-8", errors="replace").strip()
    except Exception:
        msg = str(data)
    # Strip RFC 3164 header: <PRI>Month Day HH:MM:SS hostname
    msg = re.sub(r"^<\d+>\w{3}\s+\d+\s+\d+:\d+:\d+\s+\S+\s+", "", msg)
    # Strip RFC 5424 header: <PRI>VERSION TIMESTAMP HOSTNAME APP PROCID MSGID
    msg = re.sub(r"^<\d+>\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+", "", msg)
    return msg.strip()


async def _handle(data: bytes, src_ip: str):
    tenant_id = await _lookup_tenant(src_ip)
    if not tenant_id:
        # Unknown source — log and drop (no tenant registered this IP)
        log.debug("Unknown source IP %s — dropped (not registered)", src_ip)
        return

    raw = _parse_syslog(data)
    if not raw:
        return

    record = {
        "message": raw,
        "host": src_ip,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_ip": src_ip,
    }

    await xadd("raw_syslog", tenant_id, {
        "tenant_id": tenant_id,
        "source": "syslog",
        "record": __import__("json").dumps(record),
        "received_at": datetime.now(timezone.utc).isoformat(),
    })
    log.info("tenant=%s src=%s msg=%s", tenant_id[:8], src_ip, raw[:80])


# ── UDP Protocol ─────────────────────────────────────────────────────
class SyslogUDP(asyncio.DatagramProtocol):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def datagram_received(self, data: bytes, addr):
        src_ip = addr[0]
        self._loop.create_task(_handle(data, src_ip))

    def error_received(self, exc):
        log.warning("UDP error: %s", exc)


# ── TCP Protocol ─────────────────────────────────────────────────────
async def _tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    src_ip = writer.get_extra_info("peername")[0]
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            await _handle(line, src_ip)
    except Exception:
        pass
    finally:
        writer.close()


# ── Main ─────────────────────────────────────────────────────────────
async def main():
    await connect_mongo()
    await connect_redis()

    loop = asyncio.get_running_loop()

    # UDP listener
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: SyslogUDP(loop),
            local_addr=("0.0.0.0", UDP_PORT),
        )
        log.info("UDP syslog listener started on port %d", UDP_PORT)
    except PermissionError:
        log.warning("Port %d requires root — trying 5140 instead", UDP_PORT)
        transport, _ = await loop.create_datagram_endpoint(
            lambda: SyslogUDP(loop),
            local_addr=("0.0.0.0", 5140),
        )
        log.info("UDP syslog listener started on port 5140")

    # TCP listener
    try:
        tcp_server = await asyncio.start_server(_tcp_handler, "0.0.0.0", TCP_PORT)
        log.info("TCP syslog listener started on port %d", TCP_PORT)
    except PermissionError:
        tcp_server = await asyncio.start_server(_tcp_handler, "0.0.0.0", 6014)
        log.info("TCP syslog listener started on port 6014")

    log.info("Syslog listener ready — waiting for events...")
    try:
        await asyncio.Event().wait()
    finally:
        transport.close()
        tcp_server.close()


if __name__ == "__main__":
    asyncio.run(main())
