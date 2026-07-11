import asyncio
import socket
import unittest
from unittest import mock

from discord_win_aiodns import PUBLIC_NAMESERVERS, _FallbackResolver


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
        self.assertEqual(async_resolver.call_args_list, [mock.call(), mock.call(nameservers=PUBLIC_NAMESERVERS)])
        self.assertTrue(
            any('DNS fallback is active; Cloudflare DNS resolved discord.com successfully' in entry for entry in logs.output)
        )

    def test_auto_mode_can_skip_public_dns(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=FailingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('auto', public_fallback=False, nameservers=None)
                result = asyncio.run(resolver.resolve('discord.com', 443, socket.AF_INET))

        self.assertEqual(result, [('resolved', 'discord.com', 443, socket.AF_INET)])
        async_resolver.assert_called_once_with()

    def test_public_mode_configures_cloudflare_dns(self):
        with mock.patch('discord_win_aiodns.aiohttp.AsyncResolver', return_value=WorkingResolver()) as async_resolver:
            with mock.patch('discord_win_aiodns.aiohttp.ThreadedResolver', return_value=WorkingResolver()):
                resolver = _FallbackResolver('public', public_fallback=True, nameservers=None)

        async_resolver.assert_called_once_with(nameservers=PUBLIC_NAMESERVERS)
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

        async_resolver.assert_called_once_with(nameservers=nameservers)
        asyncio.run(resolver.close())
