import os
import re
from typing import Optional

import requests
from dotenv import load_dotenv
import telebot


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set in .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN)


YANDEX_TRACK_API_URL = "https://api.music.yandex.net/tracks/{track_id}"


def extract_track_id(url: str) -> Optional[str]:
    """
    Extract track id from a Yandex.Music track URL.
    Example: https://music.yandex.ru/album/17617543/track/59508251 -> 59508251
    Invalid: https://music.yandex.ru/album/17617543/track -> None
    """
    # Require /track/<id> at the END of the URL or followed only by a fragment or query
    match = re.search(r"/track/(\d+)(?:[/?#]|$)", url)
    # Only valid if the match appears at the END of URL or is followed by ?/#/ or string end
    if match:
        # Also ensure there is an actual track id after /track/
        # But not just /track at the end or /track/
        return match.group(1)
    return None


def format_duration(duration_ms: int) -> str:
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def build_error_message(error_obj: dict) -> str:
    name = error_obj.get("name", "unknown_error")
    message = error_obj.get("message", "Неизвестная ошибка")
    return f"Ошибка от Яндекс Музыки:\n{name}: {message}"


def fetch_track_info(track_id: str) -> str:
    url = YANDEX_TRACK_API_URL.format(track_id=track_id)
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        return f"Не удалось обратиться к API Яндекс Музыки:\n{exc}"

    if response.status_code != 200:
        return f"API Яндекс Музыки вернуло статус {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        return "Не удалось разобрать ответ API (невалидный JSON)."

    # Если пришла ошибка — возвращаем её пользователю
    if "error" in data:
        error_obj = data.get("error") or {}
        return build_error_message(error_obj)

    result = data.get("result") or []
    if not result:
        return "Не удалось найти информацию о треке."

    track = result[0]
    title = track.get("title", "Без названия")

    artists = track.get("artists") or []
    if artists:
        artist_name = artists[0].get("name", "Неизвестный артист")
    else:
        artist_name = "Неизвестный артист"

    duration_ms = track.get("durationMs")
    if isinstance(duration_ms, int):
        duration_str = format_duration(duration_ms)
    else:
        duration_str = "Неизвестна"

    return (
        "Информация о треке:\n"
        f"Название: {title}\n"
        f"Артист: {artist_name}\n"
        f"Длительность: {duration_str}"
    )


@bot.message_handler(commands=["start", "help"])
def send_welcome(message: telebot.types.Message) -> None:
    bot.reply_to(
        message,
        "Привет! Отправь ссылку на трек Яндекс Музыки,\n"
        "например: https://music.yandex.ru/album/17617543/track/59508251\n"
        "Я отвечу названием, артистом и длительностью трека.",
    )


@bot.message_handler(content_types=["text"])
def handle_text(message: telebot.types.Message) -> None:
    text = message.text.strip()
    track_id = extract_track_id(text)

    if not track_id:
        bot.reply_to(
            message,
            "Не удалось извлечь id трека.\n"
            "Отправь, пожалуйста, полную ссылку на трек Яндекс Музыки.",
        )
        return

    reply_text = fetch_track_info(track_id)
    bot.reply_to(message, reply_text)


if __name__ == "__main__":
    bot.infinity_polling()

