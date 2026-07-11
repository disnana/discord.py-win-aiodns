"""Inspect the DNS servers selected by aiodns on Windows.

Run this before configuring custom nameservers. It does not contact Discord or
require a bot token.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import socket
import sys
from typing import Any, Iterable, List, Optional

import aiodns

PUBLIC_NAMESERVERS = ('1.1.1.1', '1.0.0.1')


def _channel_servers(resolver: aiodns.DNSResolver) -> Iterable[Any]:
    channel = getattr(resolver, '_channel', None)
    if channel is None:
        return ()

    servers = getattr(channel, 'servers', None)
    if callable(servers):
        servers = servers()
    return () if servers is None else servers


async def diagnose(host: str, nameservers: List[str]) -> int:
    options = {} if not nameservers else {'nameservers': nameservers}
    resolver = aiodns.DNSResolver(**options)

    print(f'Host: {host}')
    print(f'aiodns: {importlib.metadata.version("aiodns")}')
    print(f'pycares: {importlib.metadata.version("pycares")}')
    print(f'Requested nameservers: {nameservers or "automatic"}')
    print(f'c-ares nameservers: {list(_channel_servers(resolver)) or "unavailable"}')

    try:
        response = await resolver.getaddrinfo(host, port=443, type=socket.SOCK_STREAM, family=socket.AF_INET)
    except aiodns.error.DNSError as exc:
        print(f'aiodns result: FAIL {exc!r}')
        return 1

    addresses = [node.addr[0].decode('ascii') for node in response.nodes]
    print(f'aiodns result: PASS {addresses}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', nargs='?', help='host to resolve (default: discord.com)')
    parser.add_argument('--host', dest='host_option', help='host to resolve')
    nameserver_options = parser.add_mutually_exclusive_group()
    nameserver_options.add_argument('--nameserver', action='append', default=[])
    nameserver_options.add_argument('--public', action='store_true', help='test Cloudflare DNS (1.1.1.1 and 1.0.0.1)')
    arguments = parser.parse_args()

    if sys.platform != 'win32':
        print('This diagnostic is intended for Windows.', file=sys.stderr)
        return 2

    loop = asyncio.SelectorEventLoop()
    try:
        asyncio.set_event_loop(loop)
        host = arguments.host_option or arguments.host or 'discord.com'
        nameservers: Optional[List[str]] = list(PUBLIC_NAMESERVERS) if arguments.public else arguments.nameserver
        return loop.run_until_complete(diagnose(host, nameservers))
    finally:
        asyncio.set_event_loop(None)
        loop.close()


if __name__ == '__main__':
    raise SystemExit(main())
