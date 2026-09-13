"""Telegram Automation Bot Application Package."""

import socket

# Prefer IPv4 resolution to avoid 20-30s timeout delays on networks without IPv6 routing
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, *args):
    if family == 0:
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, *args)


socket.getaddrinfo = _ipv4_getaddrinfo

__version__ = "1.0.0"
