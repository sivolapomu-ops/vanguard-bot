import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = "8626377963:AAG94cRiOCV6ypUBVkPd2Nv4rJihZgm3YuU"
ADMIN_IDS = [5602309311]  # ваш Telegram ID
COMMISSION = 0.015
MIN_AMOUNT = 100

# Хранилище данных
deals_db = {}
stats_db = {"total_volume": 624042.5, "total_deals": 1247, "total_commission": 9360.64}
users_db = set()
deal_counter = 10000

# Статусы сделок:
# pending_payment - ожидает оплаты от покупателя
# payment_requested - покупатель запросил подтверждение оплаты (ждёт админа)
# payment_confirmed - админ подтвердил оплату
# goods_sent - товар отправлен, ожидает подтверждения от покупателя
# completed - сделка завершена
# cancelled - отменена

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_db.add(user.id)
    
    keyboard = [
        [InlineKeyboardButton("📝 СОЗДАТЬ СДЕЛКУ", callback_data="create_deal")],
        [InlineKeyboardButton("📊 СТАТИСТИКА", callback_data="show_stats")],
        [InlineKeyboardButton("💼 МОИ СДЕЛКИ", callback_data="my_deals")],
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ АДМИН-ПАНЕЛЬ", callback_data="admin_panel")])
    
    await update.message.reply_text(
        f"🤖 *Vanguard Trade Bot*\n\n"
        f"Добро пожаловать в гарант-сервис!\n\n"
        f"📊 *Статистика:*\n"
        f"├ Выплачено: {stats_db['total_volume']:,.1f} RUB\n"
        f"├ Всего сделок: {stats_db['total_deals']}\n"
        f"└ Комиссия: {COMMISSION * 100}%\n\n"
        f"*Как это работает:*\n"
        f"1️⃣ Продавец создаёт сделку\n"
        f"2️⃣ Покупатель переводит деньги гаранту и нажимает 'Я оплатил'\n"
        f"3️⃣ Администратор проверяет оплату и подтверждает её\n"
        f"4️⃣ Продавец отправляет товар\n"
        f"5️⃣ Покупатель подтверждает получение\n"
        f"6️⃣ Продавец получает деньги\n\n"
        f"Нажмите кнопку ниже!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text=None):
    """Показывает главное меню с кнопкой 'Назад'"""
    query = update.callback_query
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("📝 СОЗДАТЬ СДЕЛКУ", callback_data="create_deal")],
        [InlineKeyboardButton("📊 СТАТИСТИКА", callback_data="show_stats")],
        [InlineKeyboardButton("💼 МОИ СДЕЛКИ", callback_data="my_deals")],
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ АДМИН-ПАНЕЛЬ", callback_data="admin_panel")])
    
    text = message_text or "🏠 *Главное меню*\n\nВыберите действие:"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def create_deal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        "📝 *Создание сделки*\n\n"
        "Введите данные в формате:\n"
        "`@покупатель сумма описание товара`\n\n"
        "*Пример:*\n"
        "`@ivan 5000 Продажа iPhone 13 128GB`\n\n"
        f"💰 Комиссия: {COMMISSION * 100}%\n"
        f"📌 Минимальная сумма: {MIN_AMOUNT} RUB",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data['waiting_for_deal'] = True

async def handle_deal_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global deal_counter
    
    if not context.user_data.get('waiting_for_deal'):
        return
    
    user = update.effective_user
    text = update.message.text.strip().split()
    
    if len(text) < 3:
        await update.message.reply_text("❌ Неверный формат.\nИспользуйте: `@покупатель сумма описание`", parse_mode="Markdown")
        context.user_data['waiting_for_deal'] = False
        return
    
    buyer_username = text[0]
    if not buyer_username.startswith('@'):
        buyer_username = '@' + buyer_username
    
    try:
        amount = float(text[1])
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом")
        context.user_data['waiting_for_deal'] = False
        return
    
    if amount < MIN_AMOUNT:
        await update.message.reply_text(f"❌ Минимальная сумма: {MIN_AMOUNT} RUB")
        context.user_data['waiting_for_deal'] = False
        return
    
    description = ' '.join(text[2:])
    
    deal_counter += 1
    deal_number = f"VG{deal_counter}"
    
    deals_db[deal_number] = {
        "seller_id": user.id,
        "seller_username": user.username,
        "buyer_username": buyer_username,
        "buyer_id": None,
        "amount": amount,
        "commission": amount * COMMISSION,
        "seller_gets": amount * (1 - COMMISSION),
        "description": description,
        "status": "pending_payment",
        "deal_number": deal_number
    }
    
    # Клавиатура для покупателя
    buyer_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Я ОПЛАТИЛ", callback_data=f"request_payment_{deal_number}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ])
    
    await update.message.reply_text(
        f"✅ *Сделка #{deal_number} создана!*\n\n"
        f"👤 Продавец: @{user.username}\n"
        f"👤 Покупатель: {buyer_username}\n"
        f"💰 Сумма: {amount:,.2f} RUB\n"
        f"📦 Товар: {description}\n"
        f"💸 Комиссия: {amount * COMMISSION:,.2f} RUB\n"
        f"🏦 Вы получите после подтверждения: {amount * (1 - COMMISSION):,.2f} RUB\n\n"
        f"📌 *Статус:* ⏳ Ожидает оплаты от покупателя\n\n"
        f"👉 Отправьте ссылку на этого бота покупателю.\n"
        f"Покупатель должен перевести деньги на счёт гаранта и нажать 'Я оплатил'.",
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(
        f"🔔 *Сообщение для покупателя* {buyer_username}:\n\n"
        f"Продавец @{user.username} создал сделку #{deal_number}\n"
        f"Товар: {description}\n"
        f"Сумма: {amount:,.2f} RUB\n\n"
        f"💰 *Реквизиты для оплаты:*\n"
        f"Карта: **** **** **** 1234\n"
        f"Получатель: Иван Иванов\n\n"
        f"👉 После перевода денег нажмите кнопку 'Я оплатил'.\n"
        f"Администратор проверит оплату и подтвердит её.",
        reply_markup=buyer_keyboard,
        parse_mode="Markdown"
    )
    
    context.user_data['waiting_for_deal'] = False

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith('request_payment_'):
        # Покупатель нажал "Я оплатил"
        deal_number = data.split('_')[2]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        if deal['status'] != 'pending_payment':
            await query.edit_message_text(f"❌ Нельзя подтвердить оплату. Текущий статус: {deal['status']}")
            return
        
        # Обновляем статус - ждём подтверждения от админа
        deal['status'] = 'payment_requested'
        deal['buyer_id'] = query.from_user.id
        
        # Клавиатура для покупателя (ожидание)
        buyer_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(
            f"✅ *Запрос на подтверждение оплаты отправлен!*\n\n"
            f"Сделка #{deal_number}\n"
            f"Сумма: {deal['amount']:,.2f} RUB\n\n"
            f"⏳ Администратор проверяет оплату. Ожидайте подтверждения.",
            reply_markup=buyer_keyboard,
            parse_mode="Markdown"
        )
        
        # Уведомляем АДМИНОВ о необходимости подтвердить оплату
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ОПЛАТУ", callback_data=f"admin_confirm_{deal_number}")],
            [InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"admin_reject_{deal_number}")]
        ])
        
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                f"⚠️ *ТРЕБУЕТСЯ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ*\n\n"
                f"📝 Сделка: #{deal_number}\n"
                f"👤 Продавец: @{deal['seller_username']}\n"
                f"👤 Покупатель: {deal['buyer_username']}\n"
                f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
                f"📦 Товар: {deal['description']}\n\n"
                f"Покупатель утверждает, что оплатил.\n"
                f"Проверьте поступление средств и подтвердите:",
                reply_markup=admin_keyboard,
                parse_mode="Markdown"
            )
        
        # Уведомляем продавца
        await context.bot.send_message(
            deal['seller_id'],
            f"📢 *Покупатель {deal['buyer_username']} сообщил об оплате сделки #{deal_number}*\n\n"
            f"⏳ Администратор проверяет оплату. Ожидайте подтверждения.",
            parse_mode="Markdown"
        )
    
    elif data.startswith('admin_confirm_'):
        # АДМИН подтверждает оплату
        if update.effective_user.id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Доступ запрещен")
            return
        
        deal_number = data.split('_')[2]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        if deal['status'] != 'payment_requested':
            await query.edit_message_text(f"❌ Статус сделки: {deal['status']}. Ожидалось payment_requested")
            return
        
        deal['status'] = 'payment_confirmed'
        
        # Клавиатура для продавца
        seller_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 ПОДТВЕРДИТЬ ОТПРАВКУ", callback_data=f"send_goods_{deal_number}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        # Уведомляем продавца
        await context.bot.send_message(
            deal['seller_id'],
            f"✅ *АДМИНИСТРАТОР ПОДТВЕРДИЛ ОПЛАТУ!*\n\n"
            f"Сделка #{deal_number}\n"
            f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
            f"📦 Товар: {deal['description']}\n\n"
            f"👉 Отправьте товар покупателю и нажмите кнопку 'Подтвердить отправку'",
            reply_markup=seller_keyboard,
            parse_mode="Markdown"
        )
        
        # Уведомляем покупателя
        buyer_id = deal.get('buyer_id')
        if buyer_id:
            buyer_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ])
            await context.bot.send_message(
                buyer_id,
                f"✅ *АДМИНИСТРАТОР ПОДТВЕРДИЛ ВАШУ ОПЛАТУ!*\n\n"
                f"Сделка #{deal_number}\n"
                f"💰 Сумма: {deal['amount']:,.2f} RUB\n\n"
                f"⏳ Продавец скоро отправит товар.",
                reply_markup=buyer_keyboard,
                parse_mode="Markdown"
            )
        
        await query.edit_message_text(
            f"✅ *Оплата по сделке #{deal_number} подтверждена администратором!*",
            parse_mode="Markdown"
        )
    
    elif data.startswith('admin_reject_'):
        # АДМИН отклоняет оплату
        if update.effective_user.id not in ADMIN_IDS:
            await query.edit_message_text("⛔ Доступ запрещен")
            return
        
        deal_number = data.split('_')[2]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        deal['status'] = 'pending_payment'
        
        # Уведомляем покупателя
        buyer_id = deal.get('buyer_id')
        if buyer_id:
            buyer_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Я ОПЛАТИЛ", callback_data=f"request_payment_{deal_number}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ])
            await context.bot.send_message(
                buyer_id,
                f"❌ *АДМИНИСТРАТОР НЕ ПОДТВЕРДИЛ ОПЛАТУ*\n\n"
                f"Сделка #{deal_number}\n\n"
                f"Возможные причины:\n"
                f"• Оплата не поступила\n"
                f"• Неправильная сумма\n"
                f"• Неверные реквизиты\n\n"
                f"Пожалуйста, проверьте оплату и нажмите кнопку снова.",
                reply_markup=buyer_keyboard,
                parse_mode="Markdown"
            )
        
        await query.edit_message_text(
            f"❌ *Оплата по сделке #{deal_number} отклонена администратором*",
            parse_mode="Markdown"
        )
    
    elif data.startswith('send_goods_'):
        # Продавец подтверждает отправку товара
        deal_number = data.split('_')[2]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        if deal['status'] != 'payment_confirmed':
            await query.edit_message_text(f"❌ Нельзя подтвердить отправку. Текущий статус: {deal['status']}")
            return
        
        if query.from_user.id != deal['seller_id']:
            await query.edit_message_text("❌ Только продавец может подтвердить отправку")
            return
        
        deal['status'] = 'goods_sent'
        
        # Клавиатура для покупателя
        buyer_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ПОЛУЧЕНИЕ", callback_data=f"receive_goods_{deal_number}")],
            [InlineKeyboardButton("⚠️ ОТКРЫТЬ СПОР", callback_data=f"dispute_{deal_number}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        buyer_id = deal.get('buyer_id')
        if buyer_id:
            await context.bot.send_message(
                buyer_id,
                f"📦 *Продавец @{deal['seller_username']} отправил товар!*\n\n"
                f"Сделка #{deal_number}\n"
                f"📦 Товар: {deal['description']}\n\n"
                f"👉 Если получили товар, нажмите 'Подтвердить получение'.\n"
                f"⚠️ Если товар не соответствует описанию - откройте спор.",
                reply_markup=buyer_keyboard,
                parse_mode="Markdown"
            )
        
        await query.edit_message_text(
            f"✅ *Отправка товара подтверждена!*\n\n"
            f"Сделка #{deal_number}\n"
            f"Ожидайте подтверждения от покупателя.",
            parse_mode="Markdown"
        )
    
    elif data.startswith('receive_goods_'):
        # Покупатель подтверждает получение товара
        deal_number = data.split('_')[2]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        if deal['status'] != 'goods_sent':
            await query.edit_message_text(f"❌ Нельзя подтвердить получение. Текущий статус: {deal['status']}")
            return
        
        if query.from_user.id != deal.get('buyer_id'):
            await query.edit_message_text("❌ Только покупатель может подтвердить получение")
            return
        
        deal['status'] = 'completed'
        
        # Обновляем статистику
        stats_db['total_volume'] += deal['amount']
        stats_db['total_deals'] += 1
        stats_db['total_commission'] += deal['commission']
        
        # Уведомляем продавца
        seller_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        await context.bot.send_message(
            deal['seller_id'],
            f"🎉 *СДЕЛКА УСПЕШНО ЗАВЕРШЕНА!*\n\n"
            f"Сделка #{deal_number}\n"
            f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
            f"💸 Комиссия: {deal['commission']:,.2f} RUB\n"
            f"🏦 Вам перечислено: {deal['seller_gets']:,.2f} RUB\n\n"
            f"✅ Деньги зачислены на ваш счёт!",
            reply_markup=seller_keyboard,
            parse_mode="Markdown"
        )
        
        # Клавиатура для покупателя
        buyer_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(
            f"🎉 *СДЕЛКА УСПЕШНО ЗАВЕРШЕНА!*\n\n"
            f"Сделка #{deal_number}\n"
            f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
            f"📦 Товар: {deal['description']}\n\n"
            f"✅ Спасибо за использование нашего сервиса!",
            reply_markup=buyer_keyboard,
            parse_mode="Markdown"
        )
    
    elif data.startswith('dispute_'):
        # Открытие спора
        deal_number = data.split('_')[1]
        deal = deals_db.get(deal_number)
        
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена")
            return
        
        deal['status'] = 'dispute'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        
        await query.edit_message_text(
            f"⚠️ *СПОР ОТКРЫТ!*\n\n"
            f"Сделка #{deal_number}\n"
            f"Администратор будет уведомлен. Ожидайте решения.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                f"⚠️ *СПОР по сделке #{deal_number}*\n\n"
                f"👤 Продавец: @{deal['seller_username']}\n"
                f"👤 Покупатель: {deal['buyer_username']}\n"
                f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
                f"📦 Товар: {deal['description']}\n\n"
                f"Требуется вмешательство администратора.",
                parse_mode="Markdown"
            )
    
    elif data.startswith('back_to_main'):
        await show_main_menu(update, context)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    active_deals = sum(1 for d in deals_db.values() if d['status'] not in ['completed', 'cancelled'])
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    
    await query.edit_message_text(
        f"📊 *Статистика Vanguard Trade*\n\n"
        f"✅ Выплачено: {stats_db['total_volume']:,.1f} RUB\n"
        f"📈 Всего сделок: {stats_db['total_deals']}\n"
        f"🔄 Активных сделок: {active_deals}\n"
        f"💰 Собрано комиссии: {stats_db['total_commission']:,.2f} RUB\n"
        f"💸 Комиссия сервиса: {COMMISSION * 100}%",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def my_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    user_deals = []
    for num, deal in deals_db.items():
        if deal["seller_id"] == user_id or deal.get("buyer_id") == user_id:
            user_deals.append((num, deal))
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    
    if not user_deals:
        await query.edit_message_text(
            "📭 У вас пока нет сделок",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    status_emoji = {
        'pending_payment': '⏳',
        'payment_requested': '📢',
        'payment_confirmed': '✅',
        'goods_sent': '📦',
        'completed': '🎉',
        'cancelled': '❌',
        'dispute': '⚠️'
    }
    
    text = "💼 *Ваши сделки:*\n\n"
    for num, deal in user_deals[:5]:
        role = "Продавец" if deal["seller_id"] == user_id else "Покупатель"
        emoji = status_emoji.get(deal['status'], '🔄')
        text += f"{emoji} *{num}* — {deal['amount']:,.2f} RUB\n"
        text += f"   Роль: {role}\n"
        text += f"   Статус: {deal['status']}\n"
        text += f"   {deal['description'][:30]}\n\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("⛔ Доступ запрещен")
        return
    
    # Сделки, ожидающие подтверждения оплаты
    pending_payments = [num for num, d in deals_db.items() if d['status'] == 'payment_requested']
    
    keyboard = [
        [InlineKeyboardButton(f"💰 Ожидают оплаты ({len(pending_payments)})", callback_data="admin_pending_payments")],
        [InlineKeyboardButton("📋 Все активные сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    
    active_deals = sum(1 for d in deals_db.values() if d['status'] not in ['completed', 'cancelled'])
    
    await query.edit_message_text(
        f"⚙️ *Админ-панель*\n\n"
        f"📊 Всего сделок: {len(deals_db)}\n"
        f"🔄 Активных: {active_deals}\n"
        f"💰 Ожидают подтверждения оплаты: {len(pending_payments)}\n"
        f"👥 Пользователей: {len(users_db)}\n"
        f"📈 Объём: {stats_db['total_volume']:,.1f} RUB",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def admin_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает админу список сделок, ожидающих подтверждения оплаты"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("⛔ Доступ запрещен")
        return
    
    pending = [(num, d) for num, d in deals_db.items() if d['status'] == 'payment_requested']
    
    if not pending:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        await query.edit_message_text(
            "📭 Нет сделок, ожидающих подтверждения оплаты",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    keyboard = []
    for num, deal in pending[:10]:
        keyboard.append([InlineKeyboardButton(
            f"{num} - {deal['amount']} RUB - {deal['buyer_username']}",
            callback_data=f"admin_view_deal_{num}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    
    await query.edit_message_text(
        f"💰 *Сделки, ожидающие подтверждения оплаты:* {len(pending)}\n\n"
        f"Нажмите на сделку для подтверждения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def admin_view_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает админу конкретную сделку для подтверждения"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("⛔ Доступ запрещен")
        return
    
    deal_number = query.data.split('_')[3]
    deal = deals_db.get(deal_number)
    
    if not deal:
        await query.edit_message_text("❌ Сделка не найдена")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ОПЛАТУ", callback_data=f"admin_confirm_{deal_number}")],
        [InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"admin_reject_{deal_number}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_pending_payments")]
    ])
    
    await query.edit_message_text(
        f"📝 *Сделка #{deal_number}*\n\n"
        f"👤 Продавец: @{deal['seller_username']}\n"
        f"👤 Покупатель: {deal['buyer_username']}\n"
        f"💰 Сумма: {deal['amount']:,.2f} RUB\n"
        f"💸 Комиссия: {deal['commission']:,.2f} RUB\n"
        f"🏦 Продавец получит: {deal['seller_gets']:,.2f} RUB\n"
        f"📦 Товар: {deal['description']}\n"
        f"📌 Статус: {deal['status']}\n\n"
        f"Проверьте поступление средств и подтвердите:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "create_deal":
        await create_deal_start(update, context)
    elif data == "show_stats":
        await show_stats(update, context)
    elif data == "my_deals":
        await my_deals(update, context)
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "admin_pending_payments":
        await admin_pending_payments(update, context)
    elif data.startswith("admin_view_deal_"):
        await admin_view_deal(update, context)
    elif data.startswith(('request_payment_', 'admin_confirm_', 'admin_reject_', 'send_goods_', 'receive_goods_', 'dispute_', 'back_to_main')):
        await handle_payment(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deal_input))
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()