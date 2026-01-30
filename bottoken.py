from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN не найден в .env файле. Убедитесь, что .env файл существует и содержит TOKEN.")
