import re
from typing import List, Optional, Dict
from .models import TransformRules, PeerRule

SECTION_RE = re.compile(r'^\s*\[(?P<name>[^\]]+)\]\s*$', re.IGNORECASE)

def parse_wg_conf(text: str):
    sections = []
    current = {"name": None, "lines": []}
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            if current["name"]:
                sections.append(current)
            current = {"name": m.group("name").strip(), "lines": []}
        else:
            current["lines"].append(line)
    if current["name"]:
        sections.append(current)
    return sections

def kv_pairs(lines: List[str]):
    out = []
    for ln in lines:
        if "=" in ln:
            k, v = ln.split("=", 1)
            out.append((k.strip(), v.strip()))
        else:
            out.append((None, ln))
    return out

def render_section(name: str, pairs: List[tuple]):
    out = [f'[{name}]']
    for k, v in pairs:
        if k is None:
            out.append(v)
        else:
            out.append(f'{k} = {v}')
    return "\n".join(out)

def extract_keys(conf_text: str) -> Dict[str, str]:
    keys: Dict[str, str] = {}
    sections = parse_wg_conf(conf_text)
    for sec in sections:
        name = sec["name"].lower()
        pairs = kv_pairs(sec["lines"])
        if name == "interface":
            for k, v in pairs:
                if k and k.lower() == "privatekey":
                    keys["interface_private"] = v
        elif name == "peer":
            for k, v in pairs:
                if k and k.lower() == "publickey":
                    keys["peer_public"] = v
                elif k and k.lower() == "presharedkey":
                    keys["peer_preshared"] = v
    return keys

def _delete_keys(pairs: List[tuple], keys_to_delete: Optional[List[str]]) -> List[tuple]:
    if not keys_to_delete:
        return pairs
    to_del = {k.lower() for k in keys_to_delete}
    return [(k, v) for (k, v) in pairs if not (k and k.lower() in to_del)]

def apply_rules(text: str, rules: TransformRules, override_keys: Optional[Dict[str, str]] = None) -> str:
    sections = parse_wg_conf(text)
    override_keys = override_keys or {}

    for sec in sections:
        name = sec["name"].lower()
        pairs = kv_pairs(sec["lines"])

        # сначала — удаление ключей секции, если задано
        if name == "interface":
            pairs = _delete_keys(pairs, (rules.remove_interface_keys or ["ListenPort"]))
        elif name == "peer":
            pairs = _delete_keys(pairs, rules.remove_peer_keys)

        def set_or_replace(key: str, value: str):
            nonlocal pairs
            for i, (k, v) in enumerate(pairs):
                if k and k.lower() == key.lower():
                    pairs[i] = (k, value)
                    break
            else:
                pairs.append((key, value))

        if name == "interface":
            # PrivateKey: overrides > rules
            if "interface_private" in override_keys:
                set_or_replace("PrivateKey", override_keys["interface_private"])
            elif getattr(rules, "private_key", None):
                set_or_replace("PrivateKey", rules.private_key)

            # Address
            if rules.address_exact:
                set_or_replace("Address", rules.address_exact)
            elif rules.address_subnet_map:
                for i, (k, v) in enumerate(pairs):
                    if k and k.lower() == "address":
                        addrs = [a.strip() for a in v.split(",")]
                        new_addrs = []
                        for a in addrs:
                            for src, dst in rules.address_subnet_map.items():
                                if a.startswith(src):
                                    a = a.replace(src, dst, 1)
                            new_addrs.append(a)
                        pairs[i] = (k, ", ".join(new_addrs))

            # DNS
            if rules.dns_exact:
                set_or_replace("DNS", rules.dns_exact)

            # MTU
            if rules.mtu:
                set_or_replace("MTU", str(rules.mtu))

        elif name == "peer":
            pr: PeerRule = rules.peer or PeerRule()

            # Ключи пира: overrides > rules
            if "peer_public" in override_keys:
                set_or_replace("PublicKey", override_keys["peer_public"])
            elif pr.public_key:
                set_or_replace("PublicKey", pr.public_key)

            if "peer_preshared" in override_keys:
                set_or_replace("PresharedKey", override_keys["peer_preshared"])
            elif pr.preshared_key:
                set_or_replace("PresharedKey", pr.preshared_key)

            if pr.persistent_keepalive is not None:
                set_or_replace("PersistentKeepalive", str(pr.persistent_keepalive))
            if pr.endpoint:
                set_or_replace("Endpoint", pr.endpoint)
            if pr.allowed_ips:
                set_or_replace("AllowedIPs", ", ".join(pr.allowed_ips))

        sec["lines"] = [f'{k} = {v}' if k else v for k, v in pairs]

    return "\n\n".join(render_section(s["name"], kv_pairs(s["lines"])) for s in sections) + "\n"
