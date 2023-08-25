from typing import Tuple


def parse_endpoint(address: str) -> Tuple[str, str, int]:
    scheme = "http"
    fqdn = "localhost"
    port = 80
    addr = address

    addr_list = address.split("://")

    if len(addr_list) == 2:
        # A scheme was explicitly specified
        scheme = addr_list[0]
        if scheme == "https":
            port = 443
        addr = addr_list[1]

    addr_list = addr.split(":")
    if len(addr_list) == 2:
        # A port was explicitly specified
        if len(addr_list[0]) > 0:
            fqdn = addr_list[0]
        # Account for Endpoints of the type http://localhost:3500/v1.0/invoke
        addr_list = addr_list[1].split("/")
        port = addr_list[0]     # type: ignore
    elif len(addr_list) == 1:
        # No port was specified
        # Account for Endpoints of the type :3500/v1.0/invoke
        addr_list = addr_list[0].split("/")
        fqdn = addr_list[0]
    else:
        # IPv6 address
        addr_list = addr.split("]:")
        if len(addr_list) == 2:
            # A port was explicitly specified
            fqdn = addr_list[0]
            fqdn = fqdn.replace("[", "")

            addr_list = addr_list[1].split("/")
            port = addr_list[0]     # type: ignore
        elif len(addr_list) == 1:
            # No port was specified
            addr_list = addr_list[0].split("/")
            fqdn = addr_list[0]
            fqdn = fqdn.replace("[", "")
            fqdn = fqdn.replace("]", "")
        else:
            raise ValueError(f"Invalid address: {address}")

    try:
        port = int(port)
    except ValueError:
        raise ValueError(f"invalid port: {port}")

    return scheme, fqdn, port
