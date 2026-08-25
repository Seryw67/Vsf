import os
import json
from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType

# Amvera сама подставит сюда ваш секретный токен из настроек
VK_TOKEN = os.getenv("VK_TOKEN")
# Секретный код доступа для админки
SECRET_CODE = "5480"

vk_session = VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Список пользователей, которые уже ввели верный код (сбросится при перезапуске)
authorized_admins = set()

# Функция для создания клавиатуры с кнопками магазина
def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "☕ Купить чай"}, "color": "primary"},
                {"action": {"type": "text", "label": "🎭 Купить маски"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "⚙️ Панель admin"}, "color": "secondary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

# Функция для отправки сообщений пользователям
def send_message(user_id, text, keyboard=None):
    params = {"user_id": user_id, "message": text, "random_id": 0}
    if keyboard:
        params["keyboard"] = keyboard
    vk.messages.send(**params)

print("Бот магазина успешно запущен на Amvera...")

# Главный цикл чтения сообщений из ВК
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()

        # Проверка секретного кода авторизации
        if text == SECRET_CODE:
            authorized_admins.add(user_id)
            send_message(user_id, "🔒 Код верный! Вы успешно авторизовались в панели админа.")
            continue

        # Обработка обычных кнопок магазина
        if text.lower() in ["привет", "старт", "начать"]:
            send_message(user_id, "Добро пожаловать в наш магазин! Выберите нужный раздел:", get_main_keyboard())

        elif text == "☕ Купить чай":
            send_message(user_id, "Вот наш ассортимент чая:\n1. Зеленый чай\n2. Черный чай\n3. Травяной чай")

        elif text == "🎭 Купить маски":
            send_message(user_id, "Вот наши доступные маски:\n1. Медицинские маски\n2. Многоразовые тканевые маски")

        elif text == "⚙️ Панель admin":
            # Проверяем, вводил ли человек код ранее
            if user_id in authorized_admins:
                send_message(user_id, "⚙️ Добро пожаловать в Панель Администратора! Что вы хотите сделать?")
            else:
                send_message(user_id, "❌ Отказано в доступе! Пожалуйста, пришлите боту секретный код доступа (4 цифры), чтобы войти.")
