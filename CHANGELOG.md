# Changelog

All notable changes to this project are documented in this file.

## 0.1.0 - 2026-07-11

- Initial release.
- Add Windows selector-event-loop runner for discord.py clients.
- Add automatic DNS fallback from aiodns autodetection to Cloudflare DNS and
  then the Windows system resolver.
- Add explicit `public`, `system`, and `custom` resolver modes.
