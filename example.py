import os

import discord
from discord.ext import commands

from discord_win_aiodns import run

TOKEN = os.environ['DISCORD_TOKEN']

# 'auto' tries automatic aiodns DNS, Cloudflare DNS, then the Windows resolver.
# Use 'custom' with NAMESERVERS to choose a specific DNS server.
RESOLVER = 'auto'
NAMESERVERS = None

# Example custom configuration:
# RESOLVER = 'custom'
# NAMESERVERS = ['1.1.1.1']


def create_bot(connector):
    intents = discord.Intents.default()
    return commands.Bot(command_prefix='!', intents=intents, connector=connector)


run(create_bot, TOKEN, resolver=RESOLVER, nameservers=NAMESERVERS)
