# Changelog

All notable changes to this project are documented in this file.

## 0.1.1 - 2026-07-11

- Fix the Japanese README link shown on PyPI.

## 0.1.0 - 2026-07-11

- Initial release.
- Add Windows selector-event-loop runner for discord.py clients.
- Add automatic DNS fallback from aiodns autodetection to Cloudflare DNS and
  then the Windows system resolver.
- Limit fallback aiodns stages to one 1-second attempt to avoid long startup
  delays when direct DNS is unavailable.
- Add explicit `public`, `system`, and `custom` resolver modes.
