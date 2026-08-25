import os
import json
from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType

# Токен подхватывается из настроек Amvera автоматически
VK_TOKEN = os.getenv("VK_TOKEN")
# Секретный код доступа для админки
SECRET_CODE = "5480"

vk_session = VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Хранилища данных в оперативной памяти (сбрасываются при перезапуске бота)
authorized_admins = set()

# Режим пользователя (например: user_id -> "wait_tea_count" или "wait_masks_count")
user_modes = {}

# Активные заказы (user_id -> {"☕ Купить чай": "В обработке", "🎭 Купить маски": "В обработке"})
active_orders = {}

# Список всех заказов для админки (список словарей)
all_orders = []

# Главное меню магазина (зеленые кнопки покупок и синяя кнопка админа)
def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "☕ Купить чай"}, "color": "positive"},
                {"action": {"type": "text", "label": "🎭 Купить маски"}, "color": "positive"}
            ],
            [
                {"action": {"type": "text", "label": "⚙️ Панель admin"}, "color": "primary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

# Секретное меню админа, которое открывается после ввода кода
def get_admin_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "💼 Панель"}, "color": "primary"},
                {"action": {"type": "text", "label": "📁 Менеджер файлов"}, "color": "secondary"}
            ],
            [
                {"action": {"type": "text", "label": "📦 Заказы"}, "color": "positive"},
                {"action": {"type": "text", "label": "🔙 Главное меню"}, "color": "negative"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

# Функция для отправки сообщений
def send_message(user_id, text, keyboard=None):
    params = {"user_id": user_id, "message": text, "random_id": 0}
    if keyboard:
        params["keyboard"] = keyboard
    vk.messages.send(**params)

print("Бот магазина с контролем заказов успешно запущен...")

# Главный цикл чтения сообщений
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()

        # 1. Проверка секретного кода авторизации
        if text == SECRET_CODE:
            authorized_admins.add(user_id)
            send_message(user_id, "🔑 Код верный! Добро пожаловать в управление.", get_admin_keyboard())
            continue

        # 2. Перехват ввода количества товара, если пользователь находится в режиме оформления
        if user_id in user_modes:
            current_mode = user_modes[user_id]
            product_name = "☕ Чай" if current_mode == "wait_tea_count" else "🎭 Маски"
            
            # Проверяем, ввел ли пользователь число
            if not text.isdigit():
                send_message(user_id, "❌ Пожалуйста, введите корректное число цифрами (например, 5):")
                continue
                
            count = int(text)
            
            # Проверяем ограничение (До 100) и больше 0
            if count < 1 or count > 100:
                send_message(user_id, "❌ Количество должно быть от 1 до 100. Введите еще раз:")
                continue
            
            # Оформляем заказ
            if user_id not in active_orders:
                active_orders[user_id] = {}
                
            # Записываем активный заказ
            active_orders[user_id][product_name] = "В обработке"
            
            # Добавляем в общий список для админа
            order_id = len(all_orders) + 1
            all_orders.append({
                "id": order_id,
                "user_id": user_id,
                "product": product_name,
                "count": count,
                "status": "В обработке"
            })
            
            # Сбрасываем режим ожидания ввода
            del user_modes[user_id]
            
            send_message(
                user_id, 
                f"✅ Заказ №{order_id} успешно оформлен!\nТовар: {product_name}\nКоличество: {count} шт.\nСтатус: В обработке.\n\nВы не сможете заказать этот товар повторно, пока текущий заказ не будет завершен.", 
                get_main_keyboard()
            )
            continue

        # 3. Обработка обычных кнопок магазина
        if text.lower() in ["привет", "старт", "начать", "🔙 главное меню"]:
            send_message(user_id, "Добро пожаловать в наш магазин! Выберите нужный раздел:", get_main_keyboard())

        elif text == "☕ Купить чай":
            # Проверяем, есть ли уже активный заказ чая
            if user_id in active_orders and active_orders[user_id].get("☕ Чай") == "В обработке":
                send_message(user_id, "❌ Вы не можете сделать новый заказ чая! У вас уже есть активный заказ чая в статусе 'В обработке'.")
            else:
                user_modes[user_id] = "wait_tea_count"
                send_message(user_id, "Введите количество: (До 100)")

        elif text == "🎭 Купить маски":
            # Проверяем, есть ли уже активный заказ масок
            if user_id in active_orders and active_orders[user_id].get("🎭 Маски") == "В обработке":
                send_message(user_id, "❌ Вы не можете сделать новый заказ масок! У вас уже есть активный заказ масок в статусе 'В обработке'.")
            else:
                user_modes[user_id] = "wait_masks_count"
                send_message(user_id, "Введите количество: (До 100)")

        elif text == "⚙️ Панель admin":
            if user_id in authorized_admins:
                send_message(user_id, "Вы уже авторизованы. Меню админа:", get_admin_keyboard())
            else:
                send_message(user_id, "Вход в ID")

        # 4. Обработка кнопок внутри панели админа
        elif text == "💼 Панель":
            if user_id in authorized_admins:
                send_message(user_id, f"ℹ️ Статистика магазина:\nВсего заказов в системе: {len(all_orders)}")
            else:
                send_message(user_id, "❌ Доступ ограничен.")

        elif text == "📁 Менеджер файлов":
            if user_id in authorized_admins:
                send_message(user_id, "📂 Раздел разработки менеджера файлов.")
            else:
                send_message(user_id, "❌ Доступ ограничен.")

        elif text == "📦 Заказы":
            if user_id in authorized_admins:
                if not all_orders:
                    send_message(user_id, "📝 Список заказов пока пуст.")
                else:
                    orders_text = "📝 Актуальные заказы в системе:\n\n"
                    for o in all_orders:
                        orders_text += f"ID: {o['id']} | Пользователь: {o['user_id']}\nТовар: {o['product']} ({o['count']} шт.)\nСтатус: {o['status']}\n"
                        orders_text += f"Для изменения статуса отправьте команду:\n/status {o['id']} Название_статуса\n(Пример: /status {o['id']} Выполнен)\n\n"
                    send_message(user_id, orders_text)
            else:
                send_message(user_id, "❌ Доступ ограничен.")

        # Команда смены статуса для администратора (пишется текстом в чат, например: /status 1 Выполнен)
        elif text.startswith("/status ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=2)
                order_idx = int(parts[1]) - 1
                new_status = parts[2].strip()
                
                if new_status in ["Выполнен", "Закрыто", "Отказ", "В обработке"]:
                    target_order = all_orders[order_idx]
                    target_order["status"] = new_status
                    
                    target_user = target_order["user_id"]
                    target_product = target_order["product"]
                    
                    # Если статус меняется на завершающий, удаляем ограничение для пользователя
                    if new_status in ["Выполнен", "Закрыто", "Отказ"]:
                        if target_user in active_orders and target_product in active_orders[target_user]:
                            del active_orders[target_user][target_product]
                            
                    send_message(user_id, f"✅ Статус заказа №{order_idx + 1} изменен на '{new_status}'")
                    # Уведомляем клиента об изменении статуса
                    send_message(target_user, f"🔔 Статус вашего заказа на {target_product} изменился на: '{new_status}'")
                else:
                    send_message(user_id, "❌ Допустимые статусы: Выполнен, Закрыто, Отказ, В обработке")
            except Exception:
                send_message(user_id, "❌ Ошибка в формате команды. Используйте: /status [номер] [статус]")
