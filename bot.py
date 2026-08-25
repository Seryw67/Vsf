import os
import json
from datetime import datetime, timedelta
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
user_modes = {}
active_orders = {}
all_orders = []
banned_users = {}

# База предупреждений (варнов): user_id -> список словарей [{"expires": datetime, "reason": "причина"}]
user_warns = {}

# Главное меню магазина
def get_main_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "☕ Купить чай"}, "color": "positive"},
                {"action": {"type": "text", "label": "🎭 Купить маски"}, "color": "positive"}
            ],
            [
                {"action": {"type": "text", "label": "📋 Мои заказы"}, "color": "secondary"},
                {"action": {"type": "text", "label": "Вход в ID"}, "color": "primary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

# Меню админа
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

print("Бот магазина с системой банов и варнов запущен...")

# Главный цикл чтения сообщений
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()

        # 1. Проверка активных варнов (удаляем те, у которых истек срок)
        if user_id in user_warns:
            # Оставляем только те варны, время которых еще не пришло
            user_warns[user_id] = [w for w in user_warns[user_id] if w["expires"] > datetime.now()]
            if not user_warns[user_id]:
                del user_warns[user_id]

        # 2. ПРОВЕРКА НА БАН: Если пользователь в черном списке, бот полностью его игнорирует
        if user_id in banned_users:
            ban_info = banned_users[user_id]
            send_message(user_id, f"❌ Вы заблокированы в этом боте на {ban_info['days']} дн.\nПричина: {ban_info['reason']}")
            continue

        # 3. Проверка секретного кода авторизации
        if text == SECRET_CODE:
            authorized_admins.add(user_id)
            send_message(user_id, "🔑 Код верный! Добро пожаловать в управление.", get_admin_keyboard())
            continue

        # 4. Перехват ввода количества товара
        if user_id in user_modes:
            current_mode = user_modes[user_id]
            product_name = "☕ Чай" if current_mode == "wait_tea_count" else "🎭 Маски"
            
            if not text.isdigit():
                send_message(user_id, "❌ Пожалуйста, введите корректное число цифрами:")
                continue
                
            count = int(text)
            if count < 1 or count > 100:
                send_message(user_id, "❌ Количество должно быть от 1 до 100. Введите еще раз:")
                continue
            
            if user_id not in active_orders:
                active_orders[user_id] = {}
                
            active_orders[user_id][product_name] = "В обработке"
            
            order_id = len(all_orders) + 1
            all_orders.append({
                "id": order_id,
                "user_id": user_id,
                "product": product_name,
                "count": count,
                "status": "В обработке"
            })
            
            del user_modes[user_id]
            
            send_message(
                user_id, 
                f"✅ Заказ №{order_id} успешно оформлен!\nТовар: {product_name}\nКоличество: {count} шт.\nСтатус: В обработке.\n\nВы можете управлять им в разделе '📋 Мои заказы'.", 
                get_main_keyboard()
            )
            continue

        # 5. Обработка обычных кнопок магазина
        if text.lower() in ["привет", "старт", "начать", "🔙 главное меню"]:
            send_message(user_id, "Добро пожаловать в наш магазин! Выберите нужный раздел:", get_main_keyboard())

        elif text == "☕ Купить чай":
            if user_id in active_orders and active_orders[user_id].get("☕ Чай") == "В обработке":
                send_message(user_id, "❌ У вас уже есть активный заказ чая в статусе 'В обработке'. Завершите или отмените его в 'Моих заказах'.")
            else:
                user_modes[user_id] = "wait_tea_count"
                send_message(user_id, "Введите количество: (До 100)")

        elif text == "🎭 Купить маски":
            if user_id in active_orders and active_orders[user_id].get("🎭 Маски") == "В обработке":
                send_message(user_id, "❌ У вас уже есть активный заказ масок в статусе 'В обработке'. Завершите или отмените его в 'Моих заказах'.")
            else:
                user_modes[user_id] = "wait_masks_count"
                send_message(user_id, "Введите количество: (До 100)")

        elif text == "📋 Мои заказы":
            user_orders = [o for o in all_orders if o["user_id"] == user_id]
            if not user_orders:
                send_message(user_id, "ℹ️ У вас пока нет оформленных заказов.")
            else:
                response = "📋 Ваши заказы в магазине:\n\n"
                for o in user_orders:
                    response += f"📦 Заказ №{o['id']}\nТовар: {o['product']} — {o['count']} шт.\nСтатус: {o['status']}\n"
                    if o["status"] == "В обработке":
                        response += f"👉 Чтобы закрыть (отменить) этот заказ, отправьте команду:\n/cancel {o['id']}\n"
                    response += "------------------------\n"
                send_message(user_id, response)

        elif text.startswith("/cancel "):
            try:
                order_num = int(text.split())
                target_order = None
                for o in all_orders:
                    if o["id"] == order_num and o["user_id"] == user_id:
                        target_order = o
                        break
                if target_order:
                    if target_order["status"] == "В approval":
                        target_order["status"] = "Отказ"
                        prod = target_order["product"]
                        if user_id in active_orders and prod in active_orders[user_id]:
                            del active_orders[user_id][prod]
                        send_message(user_id, f"🔴 Вы успешно закрыли заказ №{order_num}. Товар '{prod}' снова доступен для покупки.")
                    else:
                        send_message(user_id, f"❌ Этот заказ нельзя закрыть, так как его текущий статус: '{target_order['status']}'.")
                else:
                    send_message(user_id, "❌ Заказ с таким номером не найден.")
            except Exception:
                send_message(user_id, "❌ Неверный формат команды. Используйте: /cancel [номер_заказа]")

        elif text == "Вход в ID":
            if user_id in authorized_admins:
                send_message(user_id, "Вы уже авторизованы. Меню admin:", get_admin_keyboard())
            else:
                send_message(user_id, "Введите ваш личный код доступа")

        # 6. Обработка кнопок внутри панели админа
        elif text == "💼 Панель":
            if user_id in authorized_admins:
                send_message(user_id, f"ℹ️ Статистика магазина:\nВсего заказов в системе: {len(all_orders)}\nЗабанено пользователей: {len(banned_users)}")
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
                    orders_text = "📝 Все заказы в системе (для Админа):\n\n"
                    for o in all_orders:
                        orders_text += f"ID: {o['id']} | Пользователь: {o['user_id']}\nТовар: {o['product']} ({o['count']} шт.)\nСтатус: {o['status']}\n"
                        orders_text += f"Для изменения статуса отправьте:\n/status {o['id']} Название_статуса\n\n"
                    send_message(user_id, orders_text)
            else:
                send_message(user_id, "❌ Доступ ограничен.")

        # КОМАНДА АДМИНА: /ban юзернейм на скок дней причина
        elif text.startswith("/ban ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=3)
                screen_name = parts[1].strip().replace("https://vk.com", "").replace("@", "")
                days = int(parts[2])
                reason = parts[3]
                vk_response = vk.utils.resolveScreenName(screen_name=screen_name)
                
                if vk_response and vk_response.get("type") == "user":
                    target_vk_id = vk_response["object_id"]
                            # КОМАНДА ДЛЯ АДМИНИСТРАТОРА: /ban юзернейм на скок дней причина
        elif text.startswith("/ban ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=3)
                screen_name = parts[1].strip().replace("https://vk.com", "").replace("://vk.com", "").replace("@", "")
                days = int(parts[2])
                reason = parts[3]
                
                vk_response = vk.utils.resolveScreenName(screen_name=screen_name)
                
                if vk_response and vk_response.get("type") == "user":
                    target_vk_id = vk_response["object_id"]
                    banned_users[target_vk_id] = {"days": days, "reason": reason}
                    send_message(user_id, f"✅ Пользователь @{screen_name} заблокирован на {days} дней. Причина: {reason}")
                    try:
                        send_message(target_vk_id, f"❌ Вы были заблокированы администратором на {days} дней.\nПричина: {reason}")
                    except Exception: 
                        pass
                else:
                    send_message(user_id, f"❌ Пользователь '{screen_name}' не найден.")
            except Exception:
                send_message(user_id, "❌ Формат: /ban [юзернейм] [дней] [причина]")

        # 🔥 НОВАЯ КОМАНДА АДМИНА: /warn юзернейм на скок дней причина
        elif text.startswith("/warn ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=3)
                screen_name = parts[1].strip().replace("https://vk.com", "").replace("://vk.com", "").replace("@", "")
                days = int(parts[2])
                reason = parts[3]
                
                vk_response = vk.utils.resolveScreenName(screen_name=screen_name)
                
                if vk_response and vk_response.get("type") == "user":
                    target_vk_id = vk_response["object_id"]
                    
                    # Рассчитываем точное время истечения варна
                    expire_time = datetime.now() + timedelta(days=days)
                    expire_str = expire_time.strftime("%d.%m.%Y %H:%M")
                    
                    if target_vk_id not in user_warns:
                        user_warns[target_vk_id] = []
                        
                    # Добавляем варн в базу
                    user_warns[target_vk_id].append({"expires": expire_time, "reason": reason})
                    current_warns_count = len(user_warns[target_vk_id])
                    
                    send_message(user_id, f"✅ Выдано предупреждение @{screen_name}.\nВсего варнов: {current_warns_count}/3\nИстекает: {expire_str}\nПричина: {reason}")
                    
                    # Автоматический БАН, если накопилось 3 активных варна
                    if current_warns_count >= 3:
                        banned_users[target_vk_id] = {"days": 30, "reason": "Накоплено 3/3 предупреждений"}
                        send_message(user_id, f"🚨 Пользователь @{screen_name} автоматически забанен на 30 дней за 3/3 варна!")
                        try:
                            send_message(target_vk_id, f"❌ Вы получили 3-е предупреждение и были забанены на 30 дней!\nПричина: {reason}")
                        except Exception: 
                            pass
                    else:
                        try:
                            send_message(target_vk_id, f"⚠️ Вам выдано предупреждение от администратора!\nВсего активных варнов: {current_warns_count}/3\nПричина: {reason}\nОно автоматически испарится: {expire_str}")
                        except Exception: 
                            pass
                else:
                    send_message(user_id, f"❌ Пользователь '{screen_name}' не найден.")
            except Exception:
                send_message(user_id, "❌ Формат: /warn [юзернейм] [дней] [причина]")

        # Команда смены статуса заказа для администратора
        elif text.startswith("/status ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=2)
                order_idx = int(parts[1]) - 1
                new_status = parts[2].strip()
                
                if new_status in ["Выполнен", "Закрыто", "Отказ", "В обработке"]:
                    target_order = all_orders[order_idx]
                    target_order["status"] = new_status
                    t_user = target_order["user_id"]
                    t_prod = target_order["product"]
                    
                    if new_status in ["Выполнен", "Закрыто", "Отказ"]:
                        if t_user in active_orders and t_prod in active_orders[t_user]:
                            del active_orders[t_user][t_prod]
                            
                    send_message(user_id, f"✅ Статус заказа №{order_idx + 1} изменен на '{new_status}'")
                    send_message(t_user, f"🔔 Статус вашего заказа №{order_idx + 1} изменился на: '{new_status}'")
                else:
                    send_message(user_id, "❌ Допустимые статусы: Выполнен, Закрыто, Отказ, В обработке")
            except Exception:
                send_message(user_id, "❌ Ошибка в формате команды. Используйте: /status [номер] [статус]")
