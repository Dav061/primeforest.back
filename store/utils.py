import telegram
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_telegram_notification(order_data):
    """Отправка уведомления в Telegram (поддерживает и объект Order, и словарь)"""
    try:
        bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Проверяем, что пришло - объект Order или словарь
        if hasattr(order_data, 'id'):  # Это объект Order
            # Формируем список товаров
            items_list = ""
            for item in order_data.items.all():
                items_list += f"\n• {item.product.name} - {item.quantity} шт. x {item.price} руб. = {item.quantity * item.price} руб."
            
            payment_method_display = dict(order_data.PAYMENT_METHODS).get(
                order_data.payment_method, order_data.payment_method
            )
            
            message = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order_data.id}</b>

👤 <b>Клиент:</b>
👤 Логин: {order_data.user.username}
📞 Телефон: {order_data.phone_number}
📍 Адрес: {order_data.address}

📦 <b>Доставка:</b>
📅 Дата: {order_data.delivery_date.strftime('%d.%m.%Y')}
⏰ Время: {order_data.delivery_time_interval}
💳 Оплата: {payment_method_display}

💰 <b>ИТОГО: {order_data.total_price} руб.</b>

🛒 <b>Товары:</b>{items_list}
"""
        else:  # Это словарь (как в вашей функции)
            message = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order_data['id']}</b>

👤 <b>Клиент:</b>
📞 Телефон: {order_data['phone']}
📍 Адрес: {order_data['address']}

📦 <b>Доставка:</b>
📅 Дата: {order_data['delivery_date']}
⏰ Время: {order_data['delivery_time']}
💳 Оплата: {order_data['payment_method']}

💰 <b>Сумма: {order_data['total']} руб.</b>

🛒 <b>Товары:</b>
"""
            for item in order_data['items']:
                message += f"\n• {item['name']} x{item['quantity']} = {item['price'] * item['quantity']} руб."
        
        # Отправляем сообщение
        bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        
        logger.info(f"Telegram notification sent successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        print(f"Ошибка отправки в Telegram: {e}")
        return False