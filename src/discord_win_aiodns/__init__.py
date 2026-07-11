"""Opt-in aiodns support for discord.py bots on Windows."""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
from typing import TYPE_CHECKING, Callable, List, Literal, Optional, Sequence, TypeVar

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult

if TYPE_CHECKING:
    import discord

__all__ = ('run',)

ClientT = TypeVar('ClientT', bound='discord.Client')
ClientFactory = Callable[[aiohttp.BaseConnector], ClientT]
ResolverMode = Literal['auto', 'aiodns', 'system', 'public', 'custom']
PUBLIC_NAMESERVERS = ('1.1.1.1', '1.0.0.1')
_log = logging.getLogger(__name__)


class _FallbackResolver(AbstractResolver):
    """Use aiodns, then Cloudflare DNS, before falling back to the system resolver."""

    def __init__(self, mode: ResolverMode, *, public_fallback: bool, nameservers: Optional[Sequence[str]]) -> None:
        self._mode = mode
        self._public_fallback = public_fallback
        self._fallback_active = False
        self._fallback_success_reported = False
        self._aiodns: Optional[aiohttp.AsyncResolver] = None
        if mode == 'public':
            self._aiodns = aiohttp.AsyncResolver(nameservers=PUBLIC_NAMESERVERS)
        elif mode == 'custom':
            assert nameservers is not None
            self._aiodns = aiohttp.AsyncResolver(nameservers=nameservers)
        elif mode != 'system':
            self._aiodns = aiohttp.AsyncResolver()
        self._threaded: aiohttp.ThreadedResolver = aiohttp.ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> List[ResolveResult]:
        while self._mode != 'system':
            try:
                assert self._aiodns is not None
                result = await self._aiodns.resolve(host, port, family=family)
                self._report_fallback_success(host)
                return result
            except OSError as exc:
                if not _is_transport_error(exc):
                    raise

                if self._mode == 'auto' and self._public_fallback:
                    _log.warning(
                        'aiodns could not contact automatically detected DNS servers; retrying with Cloudflare DNS: %s',
                        exc,
                    )
                    await self._aiodns.close()
                    self._mode = 'public'
                    self._fallback_active = True
                    self._aiodns = aiohttp.AsyncResolver(nameservers=PUBLIC_NAMESERVERS)
                    continue

                if self._mode not in ('auto', 'public', 'custom'):
                    raise

                previous_mode = self._mode
                self._mode = 'system'
                self._fallback_active = True
                _log.warning(
                    '%s aiodns resolver could not contact DNS servers; using the system resolver for the rest of this '
                    'process: %s',
                    previous_mode,
                    exc,
                )

        result = await self._threaded.resolve(host, port, family=family)
        self._report_fallback_success(host)
        return result

    async def close(self) -> None:
        if self._aiodns is not None:
            await self._aiodns.close()
        await self._threaded.close()

    def _report_fallback_success(self, host: str) -> None:
        if self._fallback_success_reported or not self._fallback_active:
            return

        resolver_name = 'Cloudflare DNS' if self._mode == 'public' else 'the Windows system resolver'
        _log.info('DNS fallback is active; %s resolved %s successfully', resolver_name, host)
        self._fallback_success_reported = True


def _is_transport_error(exc: OSError) -> bool:
    # aiohttp wraps aiodns.DNSError in OSError. These c-ares status codes mean
    # the configured DNS servers could not be contacted, not that a name is absent.
    cause = exc.__cause__
    status = cause.args[0] if cause is not None and cause.args else None
    return status in (11, 12, 26)  # ECONNREFUSED, ETIMEOUT, ENOSERVER


def _make_connector(
    mode: ResolverMode, public_fallback: bool, nameservers: Optional[Sequence[str]]
) -> aiohttp.TCPConnector:
    # This runs inside the selector event loop created by run().
    resolver = _FallbackResolver(mode, public_fallback=public_fallback, nameservers=nameservers)
    return aiohttp.TCPConnector(limit=0, resolver=resolver)


async def _start(
    client_factory: ClientFactory[ClientT],
    token: str,
    reconnect: bool,
    resolver: ResolverMode,
    public_fallback: bool,
    nameservers: Optional[Sequence[str]],
) -> None:
    connector = _make_connector(resolver, public_fallback, nameservers)
    client = client_factory(connector)

    try:
        async with client:
            await client.start(token, reconnect=reconnect)
    finally:
        await connector.close()


def run(
    client_factory: ClientFactory[ClientT],
    token: str,
    *,
    reconnect: bool = True,
    resolver: ResolverMode = 'auto',
    public_fallback: bool = True,
    nameservers: Optional[Sequence[str]] = None,
) -> None:
    """Run a discord.py client with a selector loop and a configurable resolver.

    The factory is called after the event loop starts, receiving the connector
    that must be passed to the discord.py client constructor.

    When ``resolver`` is ``'auto'``, public_fallback controls whether failed
    automatic DNS detection is retried with Cloudflare DNS.

    When ``resolver`` is ``'custom'``, nameservers is the sequence of DNS
    server addresses passed to aiodns.
    """

    if sys.platform != 'win32':
        raise RuntimeError('discord_win_aiodns is only supported on Windows')
    if resolver not in ('auto', 'aiodns', 'system', 'public', 'custom'):
        raise ValueError("resolver must be 'auto', 'aiodns', 'system', 'public', or 'custom'")
    if resolver == 'custom' and not nameservers:
        raise ValueError("nameservers must not be empty when resolver is 'custom'")
    if resolver != 'custom' and nameservers is not None:
        raise ValueError("nameservers can only be used when resolver is 'custom'")

    loop = asyncio.SelectorEventLoop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_start(client_factory, token, reconnect, resolver, public_fallback, nameservers))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
