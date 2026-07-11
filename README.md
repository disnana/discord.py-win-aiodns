# discord-py-win-aiodns

[日本語 README](README.ja.md)

`discord-py-win-aiodns` is an opt-in Windows runner for `discord.py` bots that
uses `aiodns` without modifying or monkeypatching `discord.py`.

It runs the bot in a selector event loop and supplies a public `aiohttp`
connector to the `discord.py` client. Its default resolver strategy is designed
for Windows environments where c-ares detects an unusable DNS server.

> This project is not affiliated with Discord, discord.py, aiohttp, aiodns, or
> Cloudflare.

## What it does

In the default `auto` mode, DNS resolution proceeds in this order:

1. `aiodns` with the DNS servers detected by c-ares.
2. Cloudflare DNS (`1.1.1.1` and `1.0.0.1`) through `aiodns`.
3. aiohttp's threaded system resolver, which uses Windows name resolution.

The package logs a warning when it changes stage. Once a fallback resolves a
host successfully, it logs one `INFO` message naming the active stage. A
normal successful automatic `aiodns` lookup produces no extra log entry.

Only DNS resolution is affected. This package does not guarantee that a bot as
a whole will be faster, and it does not hide connection failures.

## Requirements

- Windows
- Python 3.9 or newer
- discord.py 2.5 or newer

## Installation

```powershell
py -3 -m pip install -U discord-py-win-aiodns
```

The package installs `discord.py`, `aiohttp`, and `aiodns` as dependencies when
they are not already installed.

## Usage

Build the bot in a factory that accepts an aiohttp connector. Call `run`
instead of `bot.run`.

```python
import os

import discord
from discord.ext import commands

from discord_win_aiodns import run


def create_bot(connector):
    intents = discord.Intents.default()
    return commands.Bot(command_prefix='!', intents=intents, connector=connector)


run(create_bot, os.environ['DISCORD_TOKEN'])
```

Never hard-code or commit a Discord bot token. Set it for the current PowerShell
session before starting the bot:

```powershell
$env:DISCORD_TOKEN = 'your-token'
py .\bot.py
```

## Resolver modes

| Mode | Behaviour |
| --- | --- |
| `auto` | Use c-ares autodetection, then Cloudflare DNS, then the Windows resolver. This is the default. |
| `aiodns` | Use only the DNS servers detected by c-ares. A DNS transport failure is raised. |
| `public` | Use Cloudflare DNS through `aiodns`, then the Windows resolver if it cannot be reached. |
| `custom` | Use DNS servers supplied through `nameservers`, then the Windows resolver if they cannot be reached. |
| `system` | Use only aiohttp's threaded Windows system resolver. |

Use an explicit public-DNS-only first stage:

```python
run(create_bot, os.environ['DISCORD_TOKEN'], resolver='public')
```

Use a specific DNS server:

```python
run(
    create_bot,
    os.environ['DISCORD_TOKEN'],
    resolver='custom',
    nameservers=['1.1.1.1'],
)
```

Keep `auto` from contacting Cloudflare DNS:

```python
run(create_bot, os.environ['DISCORD_TOKEN'], public_fallback=False)
```

## Privacy and network policy

The default `auto` mode can send DNS lookups to Cloudflare after c-ares DNS
autodetection fails. Select `system`, or use
`public_fallback=False`, when the bot must not use public DNS servers. Use
`custom` when the deployment has an approved DNS resolver.

## Diagnostics

`diagnose.py` tests `aiodns` without a bot token:

```powershell
py diagnose.py
py diagnose.py --public
py diagnose.py --host gateway.discord.gg --nameserver 1.1.1.1
```

Use diagnostics before choosing a `custom` nameserver. Do not publish private
network addresses or DNS settings in an issue.

## Development

```powershell
py -3 -m pip install -e .
py -3 -m unittest discover -s tests -v
py -3 -m build
```

## Releases and PyPI publishing

The `CI` workflow runs pytest with coverage, Ruff, mypy, `pip-audit`, and
distribution checks on Windows for every pull request and push to `main`.
CodeQL scans the Python source on pull requests, pushes to `main`, and weekly.

After CI succeeds on `main`, its publish job compares the local version with
PyPI. It publishes only when the local version is newer than the latest
released version. It uses PyPI Trusted Publishing, so no PyPI token is stored
in GitHub secrets.

Before the first release, configure a PyPI pending publisher for this GitHub
repository with workflow file `ci.yml` and environment `pypi`. Then:

1. Update `version` in `pyproject.toml` and `CHANGELOG.md`.
2. Commit and push the release changes.
3. Merge the version change into `main`. CI and the publish workflow handle the
   build and distribution.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports are covered by
[SECURITY.md](SECURITY.md).

## License

This project is licensed under the [MIT License](LICENSE).
