import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import asyncio
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import logging
from flask import Flask, render_template

# Flask setup
app = Flask(__name__)

# Dictionary to store solutions
solutions = {}

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Завантаження .env
load_dotenv(".env")

# Завантаження токенів
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY or not TELEGRAM_CHANNEL:
    raise ValueError("TELEGRAM_BOT_TOKEN, OPENAI_API_KEY або TELEGRAM_CHANNEL не завантажено. Перевірте файл .env")

# Ініціалізація бота та диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Функція для перевірки підписки
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=TELEGRAM_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Помилка перевірки підписки для {user_id}: {e}")
        return False

# Команда /start
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("Привіт! Я бот і я знаю все. Чекаю на ваші завдання. Ви можете написати текст або надіслати зображення з текстом!")

# Обробка зображень
@dp.message(F.photo)
async def handle_photo(message: Message):
    try:
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_path = "temp_image.jpg"

        with open(image_path, "wb") as f:
            f.write(file.read())

        # Попередня обробка зображення
        img = Image.open(image_path)
        img = img.convert("L")
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2)

        # Розпізнавання тексту
        text = pytesseract.image_to_string(img, lang="ukr")

        if not text.strip():
            await message.answer("На зображенні не знайдено тексту.")
            return

        # Виклик OpenAI для тексту із зображення
        response = f"GPT-відповідь для тексту: {text}"  # Замініть на виклик OpenAI
        solutions[message.from_user.id] = {"task": text, "solution": response}

        # Створення клавіатури
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Розгорнути рішення", url=f"http://127.0.0.1:5000/result/{message.from_user.id}"))
        keyboard.add(InlineKeyboardButton(text="Не подобається відповідь", callback_data="dislike"))

        await message.answer("✅ Відповідь готова! Щоб її переглянути, натисніть кнопку нижче:", reply_markup=keyboard)
        os.remove(image_path)

    except Exception as e:
        await message.answer(f"Помилка під час обробки зображення: {e}")
        logging.error(f"Помилка обробки зображення: {e}")

@dp.callback_query(F.data == "dislike")
async def dislike(callback: CallbackQuery):
    await callback.message.answer("Шкода, що відповідь вам не сподобалася. Ми працюємо над покращенням!")

# Flask endpoint для міні-застосунку
@app.route("/result/<int:user_id>")
def result(user_id):
    data = solutions.get(user_id, {"task": "Дані відсутні", "solution": "Рішення недоступне"})
    return render_template("result.html", task=data["task"], solution=data["solution"])

# Основна функція для запуску
async def main():
    logging.info("Бот запускається...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        # Flask запуск
        asyncio.create_task(app.run_task("127.0.0.1", port=5000))
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Помилка при запуску бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
