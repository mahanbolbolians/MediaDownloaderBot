import socket
import logging
from hydrogram.connection.transport.tcp.tcp import TCP

logger = logging.getLogger("net_patch")

_cached_ip = None

def get_telegram_outbound_ip() -> str:
    global _cached_ip
    if _cached_ip:
        return _cached_ip

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip.startswith("127."):
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            try:
                s.bind((ip, 0))
                s.connect(("149.154.167.51", 443))
                s.close()
                _cached_ip = ip
                logger.info(f"[+] Auto-detected Telegram routing IP: {_cached_ip}")
                return _cached_ip
            except Exception:
                s.close()
    except Exception as e:
        logger.warning(f"Error probing network interfaces for Telegram: {e}")

    return None

def apply_net_patch():
    orig_connect = TCP.connect

    async def patched_connect(self, address):
        outbound_ip = get_telegram_outbound_ip()
        if outbound_ip and not self.proxy:
            try:
                self.socket.bind((outbound_ip, 0))
            except Exception:
                pass
        return await orig_connect(self, address)

    TCP.connect = patched_connect
