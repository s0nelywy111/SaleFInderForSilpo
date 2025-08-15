import telebot
from telebot import types
import re
from bs4 import BeautifulSoup as bs
import requests as req
import json
import os

# Токен бота
BOT_TOKEN = "your_API-TOKEN"

# Создание бота
bot = telebot.TeleBot(BOT_TOKEN)

def get_product_info(soup):
    """Извлекает информацию о товаре"""
    try:
        # Пробуем разные селекторы для названия
        selectors = [
            'h1.product-title',
            'h1[class*="product"]',
            '.product-info h1',
            'h1',
            '.product-name'
        ]
        
        for selector in selectors:
            name_element = soup.select_one(selector)
            if name_element:
                product_name = name_element.text.strip()
                if product_name and len(product_name) > 3:
                    return product_name
        
        return "Название не найдено"
    except Exception as e:
        return f"Ошибка извлечения: {str(e)}"

def get_price_info(soup):
    """Получает информацию о цене с учетом скидок"""
    try:
        price_info = {}
        
        # Ищем элемент с ценами
        price_container = soup.find('div', class_='product-page-price')
        if not price_container:
            return "Цена не найдена"
        
        # Извлекаем весь текст цены
        price_text = price_container.text.strip()
        
        # Ищем цены в тексте
        prices = re.findall(r'(\d+\.?\d*)\s*грн', price_text)
        
        # Ищем процент скидки
        discount_match = re.search(r'-(\d+)\s*%', price_text)
        
        if len(prices) >= 2:
            # Есть скидка
            current_price = float(prices[0])
            old_price = float(prices[1])
            discount = discount_match.group(1) if discount_match else None
            
            price_info = {
                'current_price': current_price,
                'old_price': old_price,
                'discount_percent': discount,
                'formatted': f"{current_price} грн (было {old_price} грн, скидка -{discount}%)" if discount else f"{current_price} грн (было {old_price} грн)"
            }
        elif len(prices) == 1:
            # Нет скидки
            current_price = float(prices[0])
            price_info = {
                'current_price': current_price,
                'old_price': None,
                'discount_percent': None,
                'formatted': f"{current_price} грн"
            }
        else:
            return "Цена не найдена"
        
        return price_info
        
    except Exception as e:
        return f"Ошибка получения цены: {str(e)}"

# Файл для сохранения данных
DATA_FILE = '/tracked_products.json'

def load_tracked_products():
    """Загружает отслеживаемые товары"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return {}

def save_tracked_products(data):
    """Сохраняет отслеживаемые товары"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def extract_price_number(price_text):
    """Извлекает число из текста цены"""
    numbers = re.findall(r'[\d,]+\.?\d*', price_text.replace(',', '.'))
    if numbers:
        try:
            return float(numbers[0])
        except:
            return None
    return None

def create_main_keyboard():
    """Создает основную клавиатуру"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_list = types.KeyboardButton("📋 Мои товары")
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_add = types.KeyboardButton("➕ Добавить товар")
    btn_check = types.KeyboardButton("🔄 Проверить цены")
    keyboard.add(btn_add, btn_list)
    keyboard.add(btn_check, btn_help)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    keyboard = create_main_keyboard()
    bot.reply_to(message, 
        "🛒 Привет! Я бот для отслеживания цен в Silpo!\n"
        "Выбери действие или отправь ссылку на товар:",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda message: message.text == "📋 Мои товары")
def show_my_products(message):
    """Показывает список отслеживаемых товаров"""
    user_id = str(message.from_user.id)
    tracked_data = load_tracked_products()
    
    if user_id not in tracked_data or not tracked_data[user_id]:
        bot.reply_to(message, "📭 У вас нет отслеживаемых товаров")
        return
    
    products = tracked_data[user_id]
    response = "📋 **Ваши отслеживаемые товары:**\n\n"
    
    for i, (url, product_data) in enumerate(products.items(), 1):
        name = product_data.get('name', 'Неизвестно')
        price_text = product_data.get('price_text', 'Цена неизвестна')
        
        if isinstance(price_text, dict):
            price_display = price_text.get('formatted', 'Цена неизвестна')
        else:
            price_display = price_text
            
        response += f"{i}. **{name}**\n💰 {price_display}\n🔗 [Ссылка]({url})\n\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "➕ Добавить товар")
def request_product_link(message):
    """Просит пользователя отправить ссылку"""
    bot.reply_to(message, 
        "🔗 Отправьте ссылку на товар с сайта Silpo:\n"
        "Например: https://silpo.ua/product/..."
    )

@bot.message_handler(func=lambda message: message.text == "🔄 Проверить цены")
def check_all_prices(message):
    """Проверяет цены всех отслеживаемых товаров"""
    user_id = str(message.from_user.id)
    tracked_data = load_tracked_products()
    
    if user_id not in tracked_data or not tracked_data[user_id]:
        bot.reply_to(message, "📭 У вас нет отслеживаемых товаров")
        return
    
    bot.reply_to(message, "🔍 Проверяю цены всех товаров...")
    
    for url, product_data in tracked_data[user_id].items():
        try:
            # Настройка заголовков
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # Запрос к сайту
            response = req.get(url, headers=headers)
            response.raise_for_status()
            
            # Парсинг HTML
            soup = bs(response.text, 'html.parser')
            
            # Получение информации
            product_name = get_product_info(soup)
            price_info = get_price_info(soup)
            
            if isinstance(price_info, dict):
                current_price = price_info['current_price']
                price_display = price_info['formatted']
            else:
                current_price = extract_price_number(str(price_info))
                price_display = str(price_info)
            
            # Проверяем изменение цены
            old_price = product_data.get('price')
            
            if current_price and old_price and current_price != old_price:
                # Обновляем цену
                tracked_data[user_id][url]['price'] = current_price
                tracked_data[user_id][url]['price_text'] = price_info
                save_tracked_products(tracked_data)
                
                if current_price < old_price:
                    discount_percent = ((old_price - current_price) / old_price) * 100
                    bot.send_message(message.chat.id, 
                        f"🔥 **СКИДКА НА ТОВАР!**\n"
                        f"📦 {product_name}\n"
                        f"💰 Новая цена: {price_display}\n"
                        f"📉 Снижение на {discount_percent:.1f}%\n"
                        f"🔗 {url}",
                        parse_mode='Markdown'
                    )
                elif current_price > old_price:
                    increase_percent = ((current_price - old_price) / old_price) * 100
                    bot.send_message(message.chat.id, 
                        f"📈 **ЦЕНА ВЫРОСЛА**\n"
                        f"📦 {product_name}\n"
                        f"💰 Новая цена: {price_display}\n"
                        f"📈 Рост на {increase_percent:.1f}%\n"
                        f"🔗 {url}",
                        parse_mode='Markdown'
                    )
            else:
                # Цена не изменилась
                bot.send_message(message.chat.id, 
                    f"✅ **{product_name}**\n"
                    f"💰 Цена: {price_display}\n"
                    f"📊 Без изменений"
                )
                
        except Exception as e:
            bot.send_message(message.chat.id, 
                f"❌ Ошибка при проверке товара:\n"
                f"🔗 {url}\n"
                f"⚠️ {str(e)}"
            )
    
    bot.reply_to(message, "✅ Проверка цен завершена!")

@bot.message_handler(func=lambda message: "Помощь" in message.text)
def help_command(message):
    """Обработчик кнопки помощи"""
    help_text = """
🔧 **Доступные функции:**

➕ **Добавить товар** - Добавить новый товар для отслеживания
📋 **Мои товары** - Показать список отслеживаемых товаров
🔄 **Проверить цены** - Проверить актуальные цены всех товаров
❓ **Помощь** - Показать это сообщение

📝 **Как использовать:**
1. Нажмите "➕ Добавить товар" или просто отправьте ссылку
2. Бот запомнит товар и будет следить за ценой
3. При изменении цены вы получите уведомление

🔗 **Поддерживаемые ссылки:** silpo.ua
👤 Support/Developer: @Bwrbqrhrqjg
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: 'silpo.ua' in message.text)
def handle_silpo_link(message):
    """Обработчик ссылок Silpo"""
    try:
        bot.reply_to(message, "🔍 Анализирую товар...")
        
        url = message.text.strip()
        user_id = str(message.from_user.id)
        
        # Настройка заголовков
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Запрос к сайту
        response = req.get(url, headers=headers)
        response.raise_for_status()
        
        # Парсинг HTML
        soup = bs(response.text, 'html.parser')
        
        # Получение информации
        product_name = get_product_info(soup)
        price_info = get_price_info(soup)
        
        if isinstance(price_info, dict):
            current_price = price_info['current_price']
            price_display = price_info['formatted']
        else:
            current_price = extract_price_number(str(price_info))
            price_display = str(price_info)
        
        # Загружаем существующие данные
        tracked_data = load_tracked_products()
        
        # Инициализируем пользователя если его нет
        if user_id not in tracked_data:
            tracked_data[user_id] = {}
        
        # Проверяем есть ли уже этот товар у пользователя
        product_key = url
        if product_key in tracked_data[user_id]:
            old_price = tracked_data[user_id][product_key]['price']
            
            # Обновляем цену
            tracked_data[user_id][product_key]['price'] = current_price
            tracked_data[user_id][product_key]['price_text'] = price_info
            save_tracked_products(tracked_data)
            
            # Проверяем скидку
            if current_price and old_price and current_price < old_price:
                discount_percent = ((old_price - current_price) / old_price) * 100
                bot.reply_to(message, f"🔥 СКИДКА! Цена снизилась на {discount_percent:.1f}%!")
            
            result_message = f"""
📦 **Товар:** {product_name}
💰 **Цена:** {price_display}
📊 **Статус:** Уже отслеживается
🔗 **Ссылка:** {url}
            """
        else:
            # Добавляем новый товар
            tracked_data[user_id][product_key] = {
                'name': product_name,
                'price': current_price,
                'price_text': price_info,
                'url': url
            }
            save_tracked_products(tracked_data)
            
            # Маскируем ссылку
            masked_url = f"[Открыть товар]({url})"
            
            # Формируем сообщение БЕЗ ссылки
            result_message = f"""
📦 **Товар:** {product_name}
💰 **Цена:** {price_display}
✅ **Статус:** Добавлен в отслеживание
        """
        
        bot.reply_to(message, result_message, 
                    parse_mode='Markdown',
                    disable_web_page_preview=True)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при обработке: {str(e)}")

if __name__ == "__main__":
    from pathlib import Path
    
    # Создаем файл блокировки
    lock_file = Path("bot.lock")
    lock_file.touch()
    
    try:
        print("🤖 Бот запущен!")
        bot.polling()
    finally:
        lock_file.unlink(missing_ok=True)
        print("🛑 Бот остановлен!")
