import asyncio
import socket
import sys
import unittest
from unittest import mock

import discord_win_aiodns
from discord_win_aiodns import FALLBACK_TIMEOUT, FALLBACK_TRIES, PUBLIC_NAMESERVERS, _FallbackResolver


class FailingResolver:
    async def resolve(self, host, port, family):
        try:
            raise RuntimeError(11, 'Could not contact DNS servers')
        except RuntimeError as cause:
            raise OSError(None, 'Could not contact DNS servers') from cause

    async def close(self):
        pass


class WorkingResolver:
    async def resolve(self, host, port, family):
        return [('resolved', host, port, family)]

    async def close(self):
        pass


class FakeConnector:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self):
        self.entered = False
        self.exited = False
        self.started_with = None

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True

    async def start(self, token, *, reconnect):
        self.started_with = (token, reconnect)


class FallbackResolverTests(unittest.TestCase):
    def test_auto_mode_retries_with_cloudflare_dns(self):
        with mock.patch(
            'discord_win_aiodns.aiohttp.AsyncResolver', side_effect=[FailingResolver(), WorkingResolver()]
        ) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('auto', public_fallback=True, nameservers=None)
                with self.assertLogs('discord_win_aiodns', level='INFO') as logs:
                    result = asyncio.run(resolver.resolve('discord.com', 443, socket.AF_INET))

        self.assertEqual(result, [('resolved', 'discord.com', 443, socket.AF_INET)])
        self.assertEqual(
            async_resolver.call_args_list,
            [
                mock.call(timeout=FALLBACK_TIMEOUT, tries=FALLBACK_TRIES),
                mock.call(nameservers=PUBLIC_NAMESERVERS, timeout=FALLBACK_TIMEOUT, tries=FALLBACK_TRIES),
            ],
        )
        self.assertTrue(
            any('DNS fallback is active; Cloudflare DNS resolved discord.com successfully' in entry for entry in logs.output)
        )

    def test_auto_mode_can_skip_public_dns(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=FailingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('auto', public_fallback=False, nameservers=None)
                result = asyncio.run(resolver.resolve('discord.com', 443, socket.AF_INET))

        self.assertEqual(result, [('resolved', 'discord.com', 443, socket.AF_INET)])
        async_resolver.assert_called_once_with(timeout=FALLBACK_TIMEOUT, tries=FALLBACK_TRIES)

    def test_auto_mode_uses_system_resolver_after_public_dns_fails(self):
        with mock.patch(
            'discord_win_aiodns.aiohttp.AsyncResolver', side_effect=[FailingResolver(), FailingResolver()]
        ):
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('auto', public_fallback=True, nameservers=None)
                with self.assertLogs('discord_win_aiodns', level='INFO') as logs:
                    result = asyncio.run(resolver.resolve('discord.com', 443, socket.AF_INET))

        self.assertEqual(result, [('resolved', 'discord.com', 443, socket.AF_INET)])
        self.assertTrue(
            any('the Windows system resolver resolved discord.com successfully' in entry for entry in logs.output)
        )

    def test_public_mode_configures_cloudflare_dns(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=WorkingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('public', public_fallback=True, nameservers=None)

        async_resolver.assert_called_once_with(
            nameservers=PUBLIC_NAMESERVERS, timeout=FALLBACK_TIMEOUT, tries=FALLBACK_TRIES
        )
        asyncio.run(resolver.close())

    def test_aiodns_mode_preserves_aiodns_defaults(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=WorkingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('aiodns', public_fallback=True, nameservers=None)

        async_resolver.assert_called_once_with()
        asyncio.run(resolver.close())

    def test_does_not_fallback_for_missing_name(self):
        class MissingNameResolver(FailingResolver):
            async def resolve(self, host, port, family):
                try:
                    raise RuntimeError(4, 'Domain name not found')
                except RuntimeError as cause:
                    raise OSError(None, 'Domain name not found') from cause

        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=MissingNameResolver()):
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('auto', public_fallback=True, nameservers=None)
                with self.assertRaises(OSError):
                    asyncio.run(resolver.resolve('missing.invalid', 443, socket.AF_INET))

    def test_custom_mode_configures_requested_nameservers(self):
        nameservers = ['1.1.1.1']
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=WorkingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('custom', public_fallback=True, nameservers=nameservers)

        async_resolver.assert_called_once_with(nameservers=nameservers, timeout=FALLBACK_TIMEOUT, tries=FALLBACK_TRIES)
        asyncio.run(resolver.close())

    def test_custom_mode_uses_system_resolver_after_dns_failure(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=FailingResolver()):
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('custom', public_fallback=True, nameservers=['1.1.1.1'])
                result = asyncio.run(resolver.resolve('discord.com', 443, socket.AF_INET))

        self.assertEqual(result, [('resolved', 'discord.com', 443, socket.AF_INET)])


class RunValidationTests(unittest.TestCase):
    def test_rejects_invalid_resolver_mode(self):
        from discord_win_aiodns import run

        with self.assertRaises(ValueError):
            run(lambda connector: None, 'token', resolver='invalid')

    def test_rejects_empty_custom_nameservers(self):
        from discord_win_aiodns import run

        with self.assertRaises(ValueError):
            run(lambda connector: None, 'token', resolver='custom')

    def test_rejects_nameservers_without_custom_mode(self):
        from discord_win_aiodns import run

        with self.assertRaises(ValueError):
            run(lambda connector: None, 'token', nameservers=['1.1.1.1'])

    def test_rejects_non_windows_platform(self):
        from discord_win_aiodns import run

        with mock.patch.object(sys, 'platform', 'linux'):
            with self.assertRaises(RuntimeError):
                run(lambda connector: None, 'token')

    def test_make_connector_uses_fallback_resolver(self):
        fallback = object()
        connector = object()
        with mock.patch('discord_win_aiodns._FallbackResolver', return_value=fallback) as resolver_class:
            with mock.patch('discord_win_aiodns.aiohttp.TCPConnector', return_value=connector) as connector_class:
                result = discord_win_aiodns._make_connector('system', False, None)

        self.assertIs(result, connector)
        resolver_class.assert_called_once_with('system', public_fallback=False, nameservers=None)
        connector_class.assert_called_once_with(limit=0, resolver=fallback)

    def test_start_closes_client_and_connector(self):
        connector = FakeConnector()
        client = FakeClient()
        with mock.patch('discord_win_aiodns._make_connector', return_value=connector):
            asyncio.run(discord_win_aiodns._start(lambda value: client, 'token', True, 'system', False, None))

        self.assertTrue(client.entered)
        self.assertTrue(client.exited)
        self.assertEqual(client.started_with, ('token', True))
        self.assertTrue(connector.closed)

    def test_run_manages_the_selector_event_loop(self):
        loop = mock.MagicMock()
        start_awaitable = object()
        with mock.patch.object(sys, 'platform', 'win32'):
            with mock.patch('discord_win_aiodns.asyncio.SelectorEventLoop', return_value=loop):
                with mock.patch('discord_win_aiodns.asyncio.set_event_loop') as set_event_loop:
                    with mock.patch('discord_win_aiodns._start', new=mock.Mock(return_value=start_awaitable)) as start:
                        discord_win_aiodns.run(lambda connector: None, 'token', resolver='system')

        start.assert_called_once_with(mock.ANY, 'token', True, 'system', True, None)
        self.assertEqual(loop.run_until_complete.call_count, 2)
        loop.close.assert_called_once_with()
        set_event_loop.assert_any_call(None)
