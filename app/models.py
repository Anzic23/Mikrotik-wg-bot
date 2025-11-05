from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class PeerRule(BaseModel):
    endpoint: Optional[str] = None
    public_key: Optional[str] = Field(None, alias="publicKey")
    preshared_key: Optional[str] = Field(None, alias="presharedKey")
    persistent_keepalive: Optional[int] = Field(None, alias="persistentKeepalive")
    allowed_ips: Optional[List[str]] = Field(None, alias="allowedIPs")

class TransformRules(BaseModel):
    # [Interface]
    private_key: Optional[str] = Field(None, alias="privateKey")
    address_subnet_map: Optional[Dict[str, str]] = None
    address_exact: Optional[str] = None
    dns_exact: Optional[str] = None
    mtu: Optional[int] = None

    # удаление ключей
    remove_interface_keys: Optional[List[str]] = None
    remove_peer_keys: Optional[List[str]] = None

    # [Peer]
    peer: Optional[PeerRule] = None

    keep_unknown_lines: bool = True
