import os
from disnake.ext import commands
from disnake import Intents
from bottoken import TOKEN

intents = Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Глобальный кэш для отслеживания созданных каналов
bot.created_channels_cache = {}

@bot.event
async def on_ready():
    print(f'{bot.user} запущен!')
    print('=' * 50)

def load_cogs():
    """Загрузка всех когов из папки cogs"""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('_'):
            try:
                bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Загружен ког: {filename[:-3]}')
            except Exception as e:
                print(f'❌ Ошибка загрузки {filename}: {e}')

if __name__ == "__main__":
    load_cogs()
    bot.run(TOKEN)
