import os
import json
from datetime import datetime, timedelta
from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType

# Токен подхватывается из настроек Amvera автоматически
VK_TOKEN = os.getenv("VK_TOKEN")

# СЛОВАРЬ ЛИЧНЫХ КОДОВ ДОСТУПА
STAFF_PASSWORDS = {
    "5480": {"name": "Artem_Seryw", "role": "Владелец"},
    "2808": {"name": "Wowa_Ferguson", "role": "ОСН зам"},
    "3994": {"name": "Artem_Grozov", "role": "Зам"},
    "7427": {"name": "Artemka_Milikyway", "role": "ЛД Бат ОПГ"}
}

vk_session = VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
# Хранилища данных в оперативной памяти
authorized_admins = set()
user_modes = {}
active_orders = {}
banned_users = {}
user_warns = {}
all_shop_users = set()

# Список всех заказов (будет загружаться из вечного файла в /data)
all_orders = []

# =====================================================================
# ФУНКЦИИ ДЛЯ НАСТОЯЩЕГО СОХРАНЕНИЯ ЗАКАЗОВ В ПАПКУ /data
# =====================================================================
def save_orders_to_file():
    try:
        with open("/data/orders_db.json", "w", encoding="utf-8") as f:
            json.dump(all_orders, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения заказов: {e}")

def load_orders_from_file():
    global all_orders
    try:
        if os.path.exists("/data/orders_db.json"):
            with open("/data/orders_db.json", "r", encoding="utf-8") as f:
                all_orders = json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки заказов: {e}")

# Автоматически загружаем сохраненные заказы при старте бота
load_orders_from_file()
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
                {"action": {"type": "text", "label": "📦 Заказы"}, "color": "positive"}
            ],
            [
                {"action": {"type": "text", "label": "📁 Менеджер файлов"}, "color": "secondary"},
                {"action": {"type": "text", "label": "📜 Список команд"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "🔴 Выйти из ID"}, "color": "negative"},
                {"action": {"type": "text", "label": "🔙 Главное меню"}, "color": "secondary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)
# Клавиатура Файлового Менеджера
def get_fm_keyboard():
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "📁 Выговоры"}, "color": "primary"},
                {"action": {"type": "text", "label": "📁 Сотрудники"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "📁 ЧС"}, "color": "primary"},
                {"action": {"type": "text", "label": "📁 Архив"}, "color": "primary"}
            ],
            [
                {"action": {"type": "text", "label": "📁 Список всех заказов"}, "color": "positive"}
            ],
            [
                {"action": {"type": "text", "label": "⚙️ Панель admin"}, "color": "secondary"}
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)

def send_message(user_id, text, keyboard=None):
    params = {"user_id": user_id, "message": text, "random_id": 0}
    if keyboard: params["keyboard"] = keyboard
    vk.messages.send(**params)

print("Бот магазина успешно перезапущен на Amvera...")

# Главный цикл чтения сообщений
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()

        all_shop_users.add(user_id)
        # 1. Очистка просроченных варнов
        if user_id in user_warns:
            user_warns[user_id] = [w for w in user_warns[user_id] if w["expires"] > datetime.now()]
            if not user_warns[user_id]: del user_warns[user_id]

        # 2. ПРОВЕРКА НА БАН
        if user_id in banned_users:
            ban_info = banned_users[user_id]
            send_message(user_id, f"❌ Вы заблокированы на {ban_info['days']} дн. Причина: {ban_info['reason']}")
            continue

        # 3. Проверка личного кода авторизации руководства (STAFF_PASSWORDS)
        if text in STAFF_PASSWORDS:
            authorized_admins.add(user_id)
            staff_info = STAFF_PASSWORDS[text]
            welcome_msg = f"🔑 Код верный!\n👤 Сотрудник: {staff_info['name']}\n💼 Должность: {staff_info['role']}\n\nДобро пожаловать в управление."
            send_message(user_id, welcome_msg, get_admin_keyboard())
            continue
        # 5. Обработка обычных кнопок магазина и команд
        if text.lower() in ["привет", "старт", "начать", "🔙 главное меню"]:
            send_message(user_id, "Добро пожаловать в наш магазин! Выберите нужный раздел:", get_main_keyboard())

        elif text == "☕ Купить чай":
            if user_id in active_orders and active_orders[user_id].get("☕ Чай") == "В обработке":
                send_message(user_id, "❌ У вас уже есть активный заказ чая в статусе 'На рассмотрении'.")
            else:
                user_modes[user_id] = "wait_tea_count"
                send_message(user_id, "Введите количество: (До 100)")

        elif text == "🎭 Купить маски":
            if user_id in active_orders and active_orders[user_id].get("🎭 Маски") == "В обработке":
                send_message(user_id, "❌ У вас уже есть активный заказ масок в статусе 'На рассмотрении'.")
            else:
                user_modes[user_id] = "wait_masks_count"
                send_message(user_id, "Введите количество: (До 20)")

        elif text == "📋 Мои заказы":
            user_orders = [o for o in all_orders if o["user_id"] == user_id]
            if not user_orders: send_message(user_id, "ℹ️ У вас пока нет оформленных заказов.")
            else:
                response = "📋 Ваши заказы в магазине:\n\n"
                for o in user_orders:
                    display_status = "На рассмотрении" if o["status"] == "В обработке" else o["status"]
                    response += f"📦 Заказ №{o['id']}\nТовар: {o['product']} — {o['count']} шт.\nСумма: {o['price']:,} руб.\nСтатус: {display_status}\n"
                    if o["status"] == "В обработке": response += f"👉 Для отмены отправьте: /c {o['id']}\n"
                    response += "------------------------\n"
                send_message(user_id, response)

        elif text.startswith("/c "):
            try:
                order_num = int(text.split())
                target_order = next((o for o in all_orders if o["id"] == order_num and o["user_id"] == user_id), None)
                if target_order and target_order["status"] == "В обработке":
                    target_order["status"] = "Отказ"
                    save_orders_to_file()
                    prod = target_order["product"]
                    if user_id in active_orders and prod in active_orders[user_id]: del active_orders[user_id][prod]
                    send_message(user_id, f"🔴 Вы успешно закрыли заказ №{order_num}. Товар '{prod}' снова доступен.", get_main_keyboard())
                else: send_message(user_id, "❌ Заказ не найден или его нельзя закрыть.")
            except Exception: send_message(user_id, "❌ Формат: /c [номер]")

        elif text == "Вход в ID":
            if user_id in authorized_admins: send_message(user_id, "Вы уже авторизованы. Меню admin:", get_admin_keyboard())
            else: send_message(user_id, "Введите ваш личный код доступа")

        elif text == "🔴 Выйти из ID":
            if user_id in authorized_admins:
                authorized_admins.remove(user_id)
                send_message(user_id, "🔒 Вы успешно вышли из системы управления.", get_main_keyboard())
            else: send_message(user_id, "❌ Вы не были авторизованы.", get_main_keyboard())
        # =====================================================================
        # 6. ОБРАБОТКА КНОПОК ПАНЕЛИ АДМИНИСТРАТОРА
        # =====================================================================
        elif text == "💼 Панель" and user_id in authorized_admins:
            send_message(user_id, f"ℹ️ Статистика:\nВсего заказов: {len(all_orders)}\nЗабанено: {len(banned_users)}\nКлиентов: {len(all_shop_users)}")

        elif text == "📁 Менеджер файлов" and user_id in authorized_admins:
            send_message(user_id, "Файловый менеджер. Выберите file ниже:", get_fm_keyboard())

        elif text == "📁 Выговоры" and user_id in authorized_admins:
            send_message(user_id, "📁 Файл [Выговоры]:\nНа данный момент выговоры у сотрудников отсутствуют.")

        elif text == "📁 Сотрудники" and user_id in authorized_admins:
            staff_text = (
                "📁 Файл [Сотрудники]:\n\n👑 КОМАНДОВАНИЕ 👑\n• Директор: @Artem_Seryw\n• ОСН зам: @Wowa_Ferguson\n• Зам: @Artem_Grozov\n• Зам: @Liza_Tomka\n\n"
                "✨ ПОМОЩНИКИ ✨\n• Помощник: @Darkness_Shadow\n\n👥 ОТРЯДЫ 👥\n• Отряд первые: @Andreyka_Bogdanov\n  — @Madara_Damirov\n  — @Paxan_Marlboro\n  — @Stas_Kapibarov\n\n"
                "🛡️ ОХРАНА / ВОДИТЕЛИ 🛡️\n• Охрана#1: [Свободно]\n• Охрана#2: @Magish_Wenzzexov\n• Водители: @Vova_Arrows\n\n📦 ДОСТАВЩИКИ 📦\n• Арендатор: @Alexs_Zews\n• Доставщик: @Dima_Sergervicn"
            )
            send_message(user_id, staff_text)

        elif text == "📁 ЧС" and user_id in authorized_admins:
            if not banned_users: send_message(user_id, "📁 Файл [ЧС]:\nВ чёрном списке никого нет.")
            else:
                chs_text = "📁 Файл [ЧС]:\n\n"
                for b_id, b_info in banned_users.items(): chs_text += f"👤 ID: {b_id} | Срок: {b_info['days']} дн. | Причина: {b_info['reason']}\n"
                send_message(user_id, chs_text)

        elif text == "📁 Архив" and user_id in authorized_admins:
            send_message(user_id, "📁 Файл [Архив]:\nАрхив пуст.")
        elif text == "📁 Список всех заказов" and user_id in authorized_admins:
            if not all_orders: send_message(user_id, "📁 Файл [Список всех заказов]:\nЗаказов пока нет.")
            else:
                report_text = "📁 Файл [Список всех заказов]:\n\n"
                for o in all_orders:
                    display_status = "На рассмотрении" if o["status"] == "В обработке" else o["status"]
                    report_text += f"👤 ID: {o['user_id']} | 📦 {o['product']} ({o['count']} шт.) | 💰 {o['price']:,} руб. | 📅 {o['date']} | 📍 {display_status}\n"
                send_message(user_id, report_text)

        elif text == "📜 Список команд" and user_id in authorized_admins:
            commands_list = "📜 Команды:\n\n📢 /post [текст]\n⛔ /ban [юзернейм] [дней] [причина]\n⚠️ /warn [юзернейм] [дней] [причина]\n📦 /s [номер] [статус]"
            send_message(user_id, commands_list)

        elif text == "📦 Заказы" and user_id in authorized_admins:
            keyboard = {
                "one_time": False,
                "buttons": [
                    [{"action": {"type": "text", "label": "📁 На рассмотрении"}, "color": "primary"}, {"action": {"type": "text", "label": "📁 Выполняются"}, "color": "primary"}],
                    [{"action": {"type": "text", "label": "📁 Выполнены"}, "color": "positive"}, {"action": {"type": "text", "label": "📁 Закрыты"}, "color": "secondary"}, {"action": {"type": "text", "label": "📁 Отказаны"}, "color": "negative"}],
                    [{"action": {"type": "text", "label": "Вход в ID"}, "color": "secondary"}]
                ]
            }
            send_message(user_id, "Выберите категорию заказов:", json.dumps(keyboard, ensure_ascii=False))

        elif text in ["📁 На рассмотрении", "📁 Выполняются", "📁 Выполнены", "📁 Закрыты", "📁 Отказаны"] and user_id in authorized_admins:
            status_map = {"📁 На рассмотрении": "В обработке", "📁 Выполняются": "Выполняются", "📁 Выполнены": "Выполнены", "📁 Закрыты": "Закрыто", "📁 Отказаны": "Отказ"}
            target_status = status_map[text]
            filtered_orders = [o for o in all_orders if o["status"] == target_status]
            if not filtered_orders:
                send_message(user_id, f"В категории '{text[2:]}' пока нет заказов.")
                continue
            buttons = []
            current_row = []
            for o in filtered_orders:
                current_row.append({"action": {"type": "text", "label": f"🔢 Заказ №{o['id']}"}, "color": "primary"})
                if len(current_row) == 3: buttons.append(current_row); current_row = []
            if current_row: buttons.append(current_row)
            buttons.append([{"action": {"type": "text", "label": "📦 Заказы"}, "color": "negative"}])
            list_text = f"Список заказов '{text[2:]}':\n\n"
            for o in filtered_orders: list_text += f"ID: {o['id']} | Товар: {o['product']} ({o['count']} шт.) — {o['price']:,} руб.\n"
            send_message(user_id, list_text + "\nВыберите номер заказа кнопкой:", json.dumps({"buttons": buttons}, ensure_ascii=False))
        elif text.startswith("🔢 Заказ №") and user_id in authorized_admins:
            try:
                order_num = int(text.replace("🔢 Заказ №", ""))
                target_order = next((o for o in all_orders if o["id"] == order_num), None)
                if target_order:
                    user_modes[user_id] = f"manage_order_{order_num}"
                    keyboard = {"buttons": [[{"action": {"type": "text", "label": "📍 Сделать: На рассмотрении"}, "color": "primary"}, {"action": {"type": "text", "label": "📍 Сделать: Выполняются"}, "color": "primary"}], [{"action": {"type": "text", "label": "📍 Сделать: Выполнены"}, "color": "positive"}, {"action": {"type": "text", "label": "📍 Сделать: Закрыты"}, "color": "secondary"}, {"action": {"type": "text", "label": "📍 Сделать: Отказаны"}, "color": "negative"}], [{"action": {"type": "text", "label": "📦 Заказы"}, "color": "secondary"}]]}
                    send_message(user_id, f"Заказ №{order_num}.\nТекущий статус: {target_order['status']}\nВыберите новый статус:", json.dumps(keyboard, ensure_ascii=False))
            except Exception: pass

        elif text.startswith("📍 Сделать: ") and user_id in authorized_admins:
            current_mode = user_modes.get(user_id, "")
            if current_mode.startswith("manage_order_"):
                try:
                    order_num = int(current_mode.replace("manage_order_", ""))
                    status_label = text.replace("📍 Сделать: ", "")
                    internal_status_map = {"На рассмотрении": "В обработке", "Выполняются": "Выполняются", "Выполнены": "Выполнены", "Закрыты": "Закрыто", "Отказаны": "Отказ"}
                    new_status = internal_status_map[status_label]
                    target_order = next((o for o in all_orders if o["id"] == order_num), None)
                    if target_order:
                        target_order["status"] = new_status
                        save_orders_to_file()
                        t_user = target_order["user_id"]
                        t_prod = target_order["product"]
                        if new_status in ["Выполнены", "Закрыто", "Отказ"]:
                            if t_user in active_orders and t_prod in active_orders[t_user]: del active_orders[t_user][t_prod]
                        del user_modes[user_id]
                        send_message(user_id, f"✅ Статус заказа №{order_num} изменен на '{status_label}'")
                        send_message(t_user, f"🔔 Статус вашего заказа №{order_num} изменился на: '{status_label}'")
                except Exception: pass
        elif text.startswith("/s ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=2)
                order_idx = int(parts) - 1
                new_status = parts.strip()
                status_mapping = {"на рассмотрении": "В обработке", "в обработке": "В обработке", "выполняются": "Выполняются", "выполнены": "Выполнены", "закрыты": "Закрыто", "закрыто": "Закрыто", "отказаны": "Отказ", "отказ": "Отказ"}
                resolved_status = status_mapping.get(new_status.lower())
                if resolved_status:
                    target_order = all_orders[order_idx]
                    target_order["status"] = resolved_status
                    save_orders_to_file()
                    t_user = target_order["user_id"]
                    t_prod = target_order["product"]
                    if resolved_status in ["Выполнены", "Закрыто", "Отказ"]:
                        if t_user in active_orders and t_prod in active_orders[t_user]: del active_orders[t_user][t_prod]
                    send_message(user_id, f"✅ Статус заказа №{order_idx + 1} изменен на '{resolved_status}'")
                    send_message(t_user, f"🔔 Статус вашего заказа №{order_idx + 1} изменился на: '{resolved_status}'")
            except Exception: send_message(user_id, "❌ Формат: /s [номер] [статус]")

        elif text.startswith("/ban ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=3)
                screen_name = parts.strip().replace("https://vk.com", "").replace("://vk.com", "").replace("@", "")
                days = int(parts)
                reason = parts
                vk_response = vk.utils.resolveScreenName(screen_name=screen_name)
                if vk_response and vk_response.get("type") == "user":
                    target_vk_id = vk_response["object_id"]
                    banned_users[target_vk_id] = {"days": days, "reason": reason}
                    send_message(user_id, f"✅ @{screen_name} заблокирован на {days} дн. Причина: {reason}")
                    try: send_message(target_vk_id, f"❌ Вы заблокированы на {days} дней. Причина: {reason}")
                    except Exception: pass
                else: send_message(user_id, f"❌ Пользователь '{screen_name}' не найден.")
            except Exception: send_message(user_id, "❌ Формат: /ban [юзернейм] [дней] [причина]")

        elif text.startswith("/warn ") and user_id in authorized_admins:
            try:
                parts = text.split(maxsplit=3)
                screen_name = parts.strip().replace("https://vk.com", "").replace("://vk.com", "").replace("@", "")
                days = int(parts)
                reason = parts
                vk_response = vk.utils.resolveScreenName(screen_name=screen_name)
                if vk_response and vk_response.get("type") == "user":
                    target_vk_id = vk_response["object_id"]
                    expire_time = datetime.now() + timedelta(days=days)
                    expire_str = expire_time.strftime("%d.%m.%Y %H:%M")
                    if target_vk_id not in user_warns: user_warns[target_vk_id] = []
                    user_warns[target_vk_id].append({"expires": expire_time, "reason": reason})
                    current_warns_count = len(user_warns[target_vk_id])
                    send_message(user_id, f"✅ Выдан варн @{screen_name}. Всего: {current_warns_count}/3. Срок: {expire_str}")
                    if current_warns_count >= 3:
                        banned_users[target_vk_id] = {"days": 30, "reason": "Накоплено 3/3 варна"}
                        send_message(user_id, f"🚨 @{screen_name} забанен на 30 дней за 3/3 варна!")
                        try: send_message(target_vk_id, f"❌ Вы получили 3-й варн и забанены на 30 дней!")
                        except Exception: pass
                    else:
                        try: send_message(target_vk_id, f"⚠️ Вам выдано предупреждение! Всего варнов: {current_warns_count}/3. Истекает: {expire_str}")
                        except Exception: pass
                else: send_message(user_id, f"❌ Пользователь '{screen_name}' не найден.")
            except Exception: send_message(user_id, "❌ Формат: /warn [юзернейм] [дней] [причина]")

        elif text.startswith("/post ") and user_id in authorized_admins:
            try:
                post_text = text.replace("/post ", "").strip()
                if not post_text: continue
                send_message(user_id, f"📢 Запуск рассылки для {len(all_shop_users)} пользователей...")
                success_count = 0
                for u_id in all_shop_users:
                    try: send_message(u_id, f"📢 ОБЪЯВЛЕНИЕ:\n\n{post_text}"); success_count += 1
                    except Exception: pass
                send_message(user_id, f"✅ Рассылка завершена! Доставлено: {success_count}/{len(all_shop_users)}.")
            except Exception: pass

        # 4. Перехват ввода количества товара (Строго в конце)
        elif user_id in user_modes:
            current_mode = user_modes[user_id]
            product_name = "☕ Чай" if current_mode == "wait_tea_count" else "🎭 Маски"
            price_per_item = 2500 if current_mode == "wait_tea_count" else 15000
            
            if not text.isdigit():
                send_message(user_id, "❌ Введите число цифрами:")
                continue
            count = int(text)
            
            if current_mode == "wait_tea_count" and (count < 1 or count > 100):
                send_message(user_id, "❌ Количество чая должно быть от 1 до 100. Введите еще раз:")
                continue
            elif current_mode == "wait_masks_count" and (count < 1 or count > 20):
                send_message(user_id, "❌ Количество масок должно быть от 1 до 20. Введите еще раз:")
                continue
            
            if user_id not in active_orders: active_orders[user_id] = {}
            active_orders[user_id][product_name] = "В обработке"
            
            total_price = count * price_per_item
            order_id = len(all_orders) + 1
            current_date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

            all_orders.append({
                "id": order_id, "user_id": user_id, "product": product_name,
                "count": count, "price": total_price, "date": current_date_str, "status": "В обработке"
            })
            
            save_orders_to_file()
            del user_modes[user_id]
            
            send_message(user_id, f"✅ Заказ №{order_id} оформлен!\nТовар: {product_name}\nКоличество: {count} шт.\n💰 Сумма: {total_price:,} руб.\nСтатус: На рассмотрении.", get_main_keyboard())
            
            admin_alert = f"🔔 Новый заказ №{order_id}!\n👤 Покупатель: {user_id}\n📦 Товар: {product_name} ({count} шт.)\n💵 Сумма: {total_price:,} руб."
            for admin in authorized_admins:
                try: send_message(admin, admin_alert)
                except Exception: pass
            continue
