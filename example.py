import os

import discord

from discord_win_aiodns import Bot

TOKEN = os.environ['DISCORD_TOKEN']

# 'auto' tries automatic aiodns DNS, Cloudflare DNS, then the Windows resolver.
# Use 'custom' with NAMESERVERS to choose a specific DNS server.
RESOLVER = 'auto'
NAMESERVERS = None

# Example custom configuration:
# RESOLVER = 'custom'
# NAMESERVERS = ['1.1.1.1']


bot = Bot(command_prefix='!', intents=discord.Intents.default(), resolver=RESOLVER, nameservers=NAMESERVERS)
bot.run(TOKEN)
