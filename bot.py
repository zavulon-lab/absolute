import os
import disnake
from disnake.ext import commands
from disnake import Intents
import traceback

try:
    from bottoken import TOKEN
except ImportError:
    print("Файл bottoken.py не найден или в нем нет переменной TOKEN")
    exit()

intents = Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print('=' * 50)
    print(f'{bot.user} успешно запущен!')
    print(f'ID: {bot.user.id}')
    print('=' * 50)

    # ── Регистрация persistent Views ──────────────────────────────────────

    # Giveaway
    try:
        from cogs.giveaway.database import load_all_active_giveaways
        from cogs.giveaway.views import GiveawayJoinView, GiveawayAdminPanel

        bot.add_view(GiveawayAdminPanel())
        for gw in load_all_active_giveaways():
            bot.add_view(GiveawayJoinView(gw["id"]))
            print(f"[GIVEAWAY] Восстановлен View: {gw['id']}")
    except Exception as e:
        print(f"[GIVEAWAY] Ошибка регистрации Views: {e}")

    # Events
    try:
        from cogs.events import EventUserView, MainAdminView, get_current_event

        bot.add_view(MainAdminView())
        current = get_current_event()
        if current:
            bot.add_view(EventUserView(current["id"]))
            print(f"[EVENTS] Восстановлен View: {current['id']}")
    except Exception as e:
        print(f"[EVENTS] Ошибка регистрации Views: {e}")

    # Applications
    try:
        from cogs.applications.submit_button import ApplicationChannelView
        from cogs.applications.review_view import ApplicationReviewView

        bot.add_view(ApplicationChannelView(bot))
        bot.add_view(ApplicationReviewView())
        print("[APPLICATIONS] Views восстановлены.")
    except Exception as e:
        print(f"[APPLICATIONS] Ошибка регистрации Views: {e}")


def load_cogs():
    cogs_path = './cogs'

    if not os.path.exists(cogs_path):
        print(f"❌ ОШИБКА: Папка {cogs_path} не найдена!")
        return

    loaded = 0
    failed = 0

    print('\n' + '=' * 50)
    print('🔄 ЗАГРУЗКА КОГОВ')
    print('=' * 50)

    skip_files = [
        'utils', 'constants', 'database', 'config',
        'submit_button', 'admin_panel', 'form_modal', 'review_view',
        'promotion_db'
    ]

    for filename in os.listdir(cogs_path):
        if filename.endswith('.py') and not filename.startswith('_'):
            cog_name = filename[:-3]
            if cog_name in skip_files:
                continue
            try:
                bot.load_extension(f'cogs.{cog_name}')
                print(f'✅ Загружен: cogs.{cog_name}')
                loaded += 1
            except Exception:
                print(f'❌ Ошибка при загрузке cogs.{cog_name}:')
                traceback.print_exc()
                failed += 1

    skip_dirs = ['__pycache__', 'utils', 'config', 'constants', 'database']

    for dirname in os.listdir(cogs_path):
        subdir_path = os.path.join(cogs_path, dirname)
        if os.path.isdir(subdir_path) and dirname not in skip_dirs:
            init_file = os.path.join(subdir_path, '__init__.py')
            if os.path.exists(init_file):
                module_path = f'cogs.{dirname}'
                try:
                    bot.load_extension(module_path)
                    print(f'✅ Загружен модуль: {module_path}')
                    loaded += 1
                except commands.ExtensionAlreadyLoaded:
                    print(f'⚠️ {module_path} уже загружен')
                except Exception:
                    print(f'❌ Ошибка при загрузке {module_path}:')
                    traceback.print_exc()
                    failed += 1
            else:
                print(f'⚠️ Пропущена папка {dirname} (нет __init__.py)')

    critical_cogs = ['cogs.events', 'cogs.giveaway']
    for cog_path in critical_cogs:
        if cog_path in bot.extensions:
            print(f'✓ {cog_path} уже загружен')
            continue
        try:
            bot.load_extension(cog_path)
            print(f'✅ Загружен (приоритет): {cog_path}')
            loaded += 1
        except commands.ExtensionAlreadyLoaded:
            print(f'✓ {cog_path} уже загружен')
        except Exception:
            print(f'❌ КРИТИЧЕСКАЯ ОШИБКА загрузки {cog_path}:')
            traceback.print_exc()
            failed += 1

    print('=' * 50)
    print(f'📊 Итого: {loaded} успешно | {failed} ошибок')
    print('=' * 50 + '\n')


if __name__ == "__main__":
    load_cogs()
    try:
        bot.run(TOKEN)
    except disnake.LoginFailure:
        print("❌ Неверный токен бота!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
