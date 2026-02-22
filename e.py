from telethon import functions
import asyncio
import re
import requests
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserAlreadyParticipantError, ChatWriteForbiddenError

# =========================
API_ID = 37368606
API_HASH = "b9b485bba1728c4a87b18d263c286e95"

HH_API_URL = "https://max1mapp.online/api/chat/v2"
HH_ADMIN_KEY = "luchshemu-truvun"

CHANNEL_USERNAME = "Wewinfree"
WATCH_BOT = "giftchannelsbot"
WIN_TEXT = "ПОЗДРАВЛЯЕМ"
NOTIFY_USER = "truvun"
# =========================

client = TelegramClient("session_bot", API_ID, API_HASH)
processed_posts = set()


# =========================
# ПРОВЕРКА РОЗЫГРЫША
# =========================

def is_giveaway_post(text: str) -> bool:
    if not text:
        return False

    text_upper = text.upper()

    if "🎁 РОЗЫГРЫШ" not in text_upper:
        return False

    keywords = ["АНАГРАММА", "ЗАГАДКА", "КВИЗ", "ПРИМЕР", "ЭМОДЗИ"]
    return any(word in text_upper for word in keywords)


# =========================
# AI ОТВЕТ
# =========================

async def get_ai_answer(text: str):
    headers = {
        "Authorization": f"Bearer {HH_ADMIN_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Это розыгрыш. Реши задачу и отправь только ответ без пояснений."
                )
            },
            {"role": "user", "content": text}
        ],
        "temperature": 0
    }

    loop = asyncio.get_event_loop()

    try:
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                HH_API_URL,
                json=payload,
                headers=headers,
                timeout=60
            )
        )

        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
            return re.split(r"\n", answer)[0]

    except Exception as e:
        print("❌ Ошибка запроса к API:", e)

    return None


# =========================
# ОТСЛЕЖИВАНИЕ ПОБЕДЫ
# =========================

@client.on(events.NewMessage(from_users=WATCH_BOT))
async def win_notifier(event):
    text = event.raw_text
    if text and WIN_TEXT in text:
        notify_message = "🏆 ВЫ ВЫИГРАЛИ!\n\n"
        match = re.search(r"https://t\.me/CryptoBot\?start=\S+", text)
        if match:
            notify_message += f"💰 Чек:\n{match.group(0)}"

        await client.send_message(NOTIFY_USER, notify_message)
        print("📩 Уведомление отправлено")


# =========================
# ОБРАБОТКА НОВОГО ПОСТА
# =========================

@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def handler(event):

    if not event.message.post:
        return

    post_id = event.message.id

    if post_id in processed_posts:
        return

    text = event.message.text
    if not text or not is_giveaway_post(text):
        return

    processed_posts.add(post_id)

    print("🎁 Найден розыгрыш")

    answer = await get_ai_answer(text)
    if not answer:
        print("❌ Ответ не получен")
        return

    try:
        channel = await client.get_entity(CHANNEL_USERNAME)

        # Получаем linked discussion-группу
        full = await client(functions.channels.GetFullChannelRequest(channel))
        linked_chat_id = full.full_chat.linked_chat_id

        if not linked_chat_id:
            print("❌ У канала нет discussion-группы")
            return

        discussion_group = await client.get_entity(linked_chat_id)

        # Вступаем если нужно
        try:
            await client(functions.channels.JoinChannelRequest(discussion_group))
        except UserAlreadyParticipantError:
            pass
        except:
            pass

        # Получаем сообщение обсуждения
        result = await client(
            functions.messages.GetDiscussionMessageRequest(
                peer=channel,
                msg_id=post_id
            )
        )

        if not result.messages:
            print("❌ Обсуждение не найдено")
            return

        discussion_msg = result.messages[0]

        # ОТПРАВКА КОММЕНТАРИЯ (ПРАВИЛЬНАЯ)
        await client.send_message(
            discussion_group,
            answer,
            reply_to=discussion_msg.id
        )

        print("🏆 Ответ отправлен:", answer)

    except ChatWriteForbiddenError:
        print("❌ Нет прав писать в discussion-группу")

    except FloodWaitError as e:
        print(f"⏳ FloodWait {e.seconds} сек")
        await asyncio.sleep(e.seconds)

    except Exception as e:
        print("❌ Ошибка отправки:", e)


# =========================
# ЗАПУСК
# =========================

async def main():
    print("🚀 Бот запущен")
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
