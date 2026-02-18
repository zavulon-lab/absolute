import os
import disnake
from disnake.ext import commands
from disnake import Intents
import traceback

# Попробуйте импортировать токен, если файла нет - ошибка
try:
    from bottoken import TOKEN
except ImportError:
    print("Файл bottoken.py не найден или в нем нет переменной TOKEN")
    exit()

# Настройка интентов
intents = Intents.all() # Лучше использовать .all() для тестов, чтобы точно всё работало
# Если хотите оставить default, то ваш вариант тоже ок, при условии галочек в Dev Portal.

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print('=' * 50)
    print(f'{bot.user} успешно запущен!')
    print(f'ID: {bot.user.id}')
    print('=' * 50)

def load_cogs():
    import os
    
    # Загрузка основных когов из корневой директории cogs/
    cogs_path = './cogs'
    
    if not os.path.exists(cogs_path):
        print(f"ОШИБКА: Папка {cogs_path} не найдена!")
        return

    # Загружаем коги из корневой директории
    for filename in os.listdir(cogs_path):
        if filename.endswith('.py') and not filename.startswith('_'):
            cog_name = filename[:-3]
            # Добавьте сюда имена ваших вспомогательных файлов
            if cog_name in [
                'utils', 'constants', 'database', 'config',
                'submit_button', 'admin_panel', 'form_modal', 'review_view'
            ]:
                continue
                
            try:
                bot.load_extension(f'cogs.{cog_name}')
                print(f'Загружен ког: {cog_name}')
            except Exception as e:
                print(f'Ошибка при загрузке {cog_name}:')
                traceback.print_exc() # Выведет полный текст ошибки

    # Загружаем коги из поддиректорий
    for dirname in os.listdir(cogs_path):
        subdir_path = os.path.join(cogs_path, dirname)
        if os.path.isdir(subdir_path):
            init_file = os.path.join(subdir_path, '__init__.py')
            if os.path.exists(init_file):
                module_path = f'cogs.{dirname}'
                
                # Исключаем вспомогательные подкаталоги
                skip_dirs = ['utils', 'config', 'constants', 'database']
                if not any(skip_dir in module_path for skip_dir in skip_dirs):
                    try:
                        bot.load_extension(module_path)
                        print(f'Загружен ког: {module_path}')
                    except Exception as e:
                        print(f'Ошибка при загрузке {module_path}:')
                        traceback.print_exc() # Выведет полный текст ошибки

if __name__ == "__main__":
    load_cogs()
    try:
        bot.run(TOKEN)
    except disnake.LoginFailure:
        print("Неверный токен бота!")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
