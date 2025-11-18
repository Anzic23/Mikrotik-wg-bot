import os
import ipaddress
import requests
import subprocess


class MikrotikAPI:
    def __init__(self):
        self.host = os.getenv("MT_HOST")
        self.port = os.getenv("MT_PORT", "443")
        self.user = os.getenv("MT_USER")
        self.password = os.getenv("MT_PASSWORD")
        self.verify_ssl = os.getenv("MT_VERIFY_SSL", "false").lower() == "true"

        self.interface = os.getenv("WG_INTERFACE", "WG_Server")
        self.dns = os.getenv("WG_DNS", "192.168.220.1")
        self.endpoint = os.getenv("WG_ENDPOINT", "77.73.67.157:53254")
        self.keepalive = os.getenv("WG_KEEPALIVE", "16")
        self.mtu = os.getenv("WG_MTU", "1280")

        pool = os.getenv("WG_POOL", "192.168.220.0/24")
        self.pool = ipaddress.ip_network(pool, strict=False)

        self.base_url = f"https://{self.host}:{self.port}/rest"
        self.auth = (self.user, self.password)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def list_peers(self):
        r = requests.get(
            self._url("/interface/wireguard/peers"),
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def next_free_ip(self) -> str:
        """Возвращает первый свободный /32 из пула WG_POOL."""
        used = set()

        for peer in self.list_peers():
            aa = (peer.get("allowed-address") or "")
            for addr in aa.split(","):
                addr = addr.strip()
                if not addr:
                    continue
                try:
                    net = ipaddress.ip_network(addr, strict=False)
                    if net.prefixlen == 32:
                        used.add(net.network_address)
                except Exception:
                    pass

        for h in self.pool.hosts():
            if h in used:
                continue
            return f"{h}/32"

        raise RuntimeError("No free IPs in pool")

    def generate_keys(self):
        """Генерирует private/public/psk с помощью wireguard-tools внутри контейнера."""
        priv = subprocess.check_output(["wg", "genkey"]).strip()
        pub = subprocess.run(
            ["wg", "pubkey"],
            input=priv,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.strip()
        psk = subprocess.check_output(["wg", "genpsk"]).strip()
        return priv.decode(), pub.decode(), psk.decode()

    def get_server_public_key(self):
        r = requests.get(
            self._url("/interface/wireguard"),
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=15,
        )
        r.raise_for_status()
        items = r.json()
        for it in items:
            if it.get("name") == self.interface:
                return it.get("public-key")
        raise RuntimeError(f"WG interface '{self.interface}' not found")

    def add_peer(self, name: str) -> str:
        """Создаёт peer на MikroTik и возвращает клиентский конфиг (без профиля AllowedIPs)."""
        private_key, public_key, preshared_key = self.generate_keys()
        allowed_address = self.next_free_ip()

        payload = {
            "interface": self.interface,
            "name": name,
            "allowed-address": allowed_address,
            "preshared-key": preshared_key,
            "public-key": public_key,
            "responder": "true",
        }

        r = requests.post(
            self._url("/interface/wireguard/peers/add"),
            auth=self.auth,
            json=payload,
            verify=self.verify_ssl,
            timeout=15,
        )
        r.raise_for_status()

        server_pub = self.get_server_public_key()
        config = (
            "[Interface]\n"
            f"PrivateKey = {private_key}\n"
            f"Address = {allowed_address}\n"
            f"DNS = {self.dns}\n"
            f"MTU = {self.mtu}\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {server_pub}\n"
            f"PresharedKey = {preshared_key}\n"
            # AllowedIPs бот потом заменяет на base / all
            "AllowedIPs = 0.0.0.0/0, ::/0\n"
            f"Endpoint = {self.endpoint}\n"
            f"PersistentKeepalive = {self.keepalive}\n"
        )
        return config
