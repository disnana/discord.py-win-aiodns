# discord-py-win-aiodns

[English README](README.md)

`discord-py-win-aiodns` は、`discord.py` 本体を変更・monkeypatch せずに
`aiodns` を利用するための、Windows 向け opt-in ランナーです。

SelectorEventLoop 上で bot を動かし、公開 API である `connector` 引数を
通じて `aiohttp` connector を `discord.py` に渡します。c-ares が利用不能な
DNS サーバーを自動検出する Windows 環境を想定して、段階的な DNS fallback を
提供します。

> このプロジェクトは Discord、discord.py、aiohttp、aiodns、Cloudflare と
> 提携・関連していません。

## 動作

既定の `auto` モードでは、DNS 解決を次の順で試みます。

1. c-ares が自動検出した DNS サーバーを `aiodns` で使う。
2. Cloudflare DNS (`1.1.1.1` と `1.0.0.1`) を `aiodns` で使う。
3. Windows の名前解決を使う aiohttp の threaded system resolver を使う。

段階を切り替える時は warning を出します。fallback 段階で初めて名前解決に
成功した時は、実際に利用中の段階を示す `INFO` をプロセスごとに一度だけ出力
します。自動検出された `aiodns` が通常どおり成功した場合、追加ログは出ません。

このライブラリが影響するのは DNS 解決だけです。bot 全体が必ず高速化することを
保証するものではなく、接続エラーを握り潰すものでもありません。

## 必要環境

- Windows
- Python 3.9 以降
- discord.py 2.5 以降

## インストール

```powershell
py -3 -m pip install -U discord-py-win-aiodns
```

未インストールの場合は、`discord.py`、`aiohttp`、`aiodns` も依存関係として
インストールされます。

## 使い方

aiohttp connector を受け取る factory 内で bot を生成し、`bot.run` の代わりに
`run` を呼びます。

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

Discord bot token をソースコードに直接書いたり commit したりしないでください。
PowerShell の現在のセッションへ設定してから起動します。

```powershell
$env:DISCORD_TOKEN = 'your-token'
py .\bot.py
```

## Resolver モード

| モード | 動作 |
| --- | --- |
| `auto` | c-ares の自動検出、Cloudflare DNS、Windows resolver の順に使います。既定値です。 |
| `aiodns` | c-ares が自動検出した DNS のみを使います。DNS 通信エラーはそのまま送出します。 |
| `public` | Cloudflare DNS を `aiodns` で使い、到達できない時は Windows resolver へ切り替えます。 |
| `custom` | `nameservers` で指定した DNS を使い、到達できない時は Windows resolver へ切り替えます。 |
| `system` | aiohttp の threaded Windows system resolver のみを使います。 |

Cloudflare DNS を最初から使う場合:

```python
run(create_bot, os.environ['DISCORD_TOKEN'], resolver='public')
```

任意の DNS サーバーを指定する場合:

```python
run(
    create_bot,
    os.environ['DISCORD_TOKEN'],
    resolver='custom',
    nameservers=['1.1.1.1'],
)
```

`auto` で Cloudflare DNS を使わない場合:

```python
run(create_bot, os.environ['DISCORD_TOKEN'], public_fallback=False)
```

## プライバシーとネットワーク方針

既定の `auto` は、c-ares の DNS 自動検出に失敗すると Cloudflare へ DNS 問い合わせ
を送ることがあります。公開 DNS を使用できない環境では `system`、または
`public_fallback=False` を選んでください。承認済みの DNS resolver がある環境では
`custom` を使ってください。

## 診断

`diagnose.py` は bot token を使わず `aiodns` を単体で確認します。

```powershell
py diagnose.py
py diagnose.py --public
py diagnose.py --host gateway.discord.gg --nameserver 1.1.1.1
```

`custom` を使う前に診断してください。private network のアドレスや DNS 設定を
Issue に投稿しないでください。

## 開発

```powershell
py -3 -m pip install -e .
py -3 -m unittest discover -s tests -v
py -3 -m build
```

## リリースと PyPI 配布

`CI` workflow は Pull Request と `main` への push ごとに Windows 上で pytest と
coverage、Ruff、mypy、`pip-audit`、配布物検証を行います。CodeQL は Pull Request、
`main` への push、毎週の定期実行で Python ソースを解析します。

`main` の CI 成功後、CI 内の publish job はローカル version と PyPI の最新公開
version を比較します。ローカル version が新しい場合だけ build と配布を行います。
PyPI Trusted Publishing を使うため、PyPI token を GitHub Secrets に保存しません。

最初のリリース前に、PyPI でこの GitHub リポジトリに対する pending publisher を
設定してください。workflow file は `ci.yml`、environment は `pypi` です。

1. `pyproject.toml` の `version` と `CHANGELOG.md` を更新します。
2. リリース用の変更を commit して push します。
3. version 更新を `main` へ merge します。CI と publish workflow が build と配布を
   行います。

## コントリビューション

[CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。セキュリティ報告は
[SECURITY.md](SECURITY.md) に従ってください。

## ライセンス

このプロジェクトは [MIT License](LICENSE) で公開します。
