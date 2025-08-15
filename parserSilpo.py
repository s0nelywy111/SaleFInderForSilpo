import re
from bs4 import BeautifulSoup as bs
import requests as req
import json
import os
import threading
import time
from datetime import datetime

# ДОБАВИТЬ ИМПОРТ БОТА:
try:
    from telegram_bot import bot, load_tracked_products, save_tracked_products, extract_price_number
except ImportError:
    print("⚠️ Telegram бот не найден, работаем без уведомлений")
    bot = None
    
    def load_tracked_products():
        return {}
    
    def save_tracked_products(data):
        pass
    
    def extract_price_number(text):
        return None

# Файл для сохранения данных
DATA_FILE = "/tracked_products.json"

# Глобальные переменные
data = None

def load_existing_data():
    """Загружает существующие данные или создает новую структуру"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return {
            "products": [],
            "links": [],
            "count": 0
        }

def save_data(data):
    """Сохраняет данные в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def logs():
    """Выводит статистику товаров"""
    global data
    if data is None:
        data = load_existing_data()
    print("📊 Всего товаров:", data['count'])
    print("📦 Товары:", data['products'])

def input_link():
    """Запрашивает у пользователя ссылку на товар"""
    global data
    if data is None:
        data = load_existing_data()
    
    choice = input("Вы хотите ввести ссылку на товар? (да/нет): ").strip().lower()
    
    if choice in ['нет', 'no', 'н', 'n']:
        if not data['products']:
            print("❌ Список товаров пуст! Добавьте товары сначала.")
            return input_link()
            
        print("📦 Выберите товар из списка:")
        for i, product in enumerate(data['products'], 1):
            print(f"{i}. {product}")
        
        try:
            # Выбор по номеру
            choice_num = int(input("Введите номер товара: ").strip())
            if 1 <= choice_num <= len(data['products']):
                selected_index = choice_num - 1
                selected_product = data['products'][selected_index]
                selected_link = data['links'][selected_index]
                print(f"✅ Выбран товар: {selected_product}")
                return selected_link, True  # True означает что товар уже сохранен
            else:
                print("❌ Неверный номер товара!")
                return input_link()
                
        except ValueError:
            # Поиск по части названия
            search_term = input("Или введите часть названия для поиска: ").strip().lower()
            matches = []
            
            for i, product in enumerate(data['products']):
                if search_term in product.lower():
                    matches.append((i, product))
            
            if not matches:
                print("❌ Товар не найден!")
                return input_link()
            elif len(matches) == 1:
                # Найден один товар
                index, product = matches[0]
                print(f"✅ Найден товар: {product}")
                return data['links'][index], True
            else:
                # Найдено несколько товаров
                print("🔍 Найдено несколько товаров:")
                for i, (_, product) in enumerate(matches, 1):
                    print(f"{i}. {product}")
                
                try:
                    choice_num = int(input("Выберите номер: ").strip())
                    if 1 <= choice_num <= len(matches):
                        index, product = matches[choice_num - 1]
                        print(f"✅ Выбран товар: {product}")
                        return data['links'][index], True
                    else:
                        print("❌ Неверный номер!")
                        return input_link()
                except ValueError:
                    print("❌ Введите число!")
                    return input_link()
    
    else:  # да или любой другой ответ
        url = input("Введите ссылку на товар: ").strip()
        if not re.match(r'https?://', url):
            print("Некорректная ссылка. Пожалуйста, введите полную ссылку.")
            return input_link()
        return url, False  # False означает что товар новый

def get_product_info(soup):
    """Извлекает информацию о товаре"""
    try:
        products_name = soup.find('h1', class_='product-page__title').text.strip()
        products_link = soup.find('link', rel='canonical')['href']
        return products_name, products_link
    except AttributeError:
        print("Ошибка: не удалось найти информацию о товаре")
        return None, None

def get_price_info(soup):
    """Получает информацию о цене и акциях"""
    price_elements = soup.find('div', class_='product-page-price')
    main_price = price_elements.find('div', class_='product-page-price__old')
    sale_price = price_elements.find('div', class_='product-page-price__main')
    sale_value = price_elements.find('div', class_='product-page-price__discount')
    price_info = f"со скидкой: {sale_price.text.strip()}\n   Основная цена: {main_price.text.strip()}\n   Скидка: {sale_value.text.strip()}" if sale_value else f"Цена: {sale_price.text.strip()}"
    return price_info

def save_product_data(products_name, products_link):
    """Сохраняет данные о товаре"""
    global data
    
    choice = input("Вы хотите сохранить данные в файл? (да/нет): ").strip().lower()
    
    if choice in ['да', 'yes', 'д', 'y']:
        if products_name not in data['products']:
            data['products'].append(products_name)
            data['links'].append(products_link)
            data['count'] += 1
            print(f"✅ Добавлен новый товар: {products_name}")
            save_data(data)
        else:
            print(f"⚠️ Товар уже существует: {products_name}")
    else:
        print("Данные не сохранены.")

def send_notification_to_user(user_id, message_text):
    """Отправляет уведомление конкретному пользователю"""
    try:
        bot.send_message(user_id, message_text, 
                        parse_mode='Markdown',
                        disable_web_page_preview=True)
        print(f"✅ Уведомление отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")

def monitor_all_users():
    """Мониторинг цен для всех пользователей"""
    while True:
        try:
            print(f"🔍 Проверка цен в {datetime.now().strftime('%H:%M:%S')}")
            tracked_data = load_tracked_products()
            
            for user_id, products in tracked_data.items():
                for url, product_data in products.items():
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
                            # Обновляем цену в файле
                            tracked_data[user_id][url]['price'] = current_price
                            tracked_data[user_id][url]['price_text'] = price_info
                            save_tracked_products(tracked_data)
                            
                            if current_price < old_price:
                                # СКИДКА!
                                discount_percent = ((old_price - current_price) / old_price) * 100
                                notification = f"""
🔥 **СКИДКА НА ТОВАР!**
📦 {product_name}
💰 Новая цена: {price_display}
📉 Снижение на {discount_percent:.1f}%
🔗 {url}
⏰ {datetime.now().strftime('%H:%M, %d.%m.%Y')}
                                """
                                send_notification_to_user(user_id, notification)
                                
                            elif current_price > old_price:
                                # ЦЕНА ВЫРОСЛА
                                increase_percent = ((current_price - old_price) / old_price) * 100
                                notification = f"""
📈 **ЦЕНА ВЫРОСЛА**
📦 {product_name}
💰 Новая цена: {price_display}
📈 Рост на {increase_percent:.1f}%
🔗 {url}
⏰ {datetime.now().strftime('%H:%M, %d.%m.%Y')}
                                """
                                send_notification_to_user(user_id, notification)
                        
                        # Небольшая пауза между запросами
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"❌ Ошибка при проверке товара {url}: {e}")
                        
            print("✅ Проверка цен завершена")
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
        
        # Ждем 30 минут до следующей проверки
        time.sleep(1800)  # 30 минут

def start_monitoring():
    """Запускает мониторинг в отдельном потоке"""
    monitor_thread = threading.Thread(target=monitor_all_users, daemon=True)
    monitor_thread.start()
    print("🚀 Автоматический мониторинг запущен!")

# Добавь команду для управления мониторингом
@bot.message_handler(commands=['start_monitoring'])
def cmd_start_monitoring(message):
    """Команда для запуска мониторинга"""
    start_monitoring()
    bot.reply_to(message, 
        "🚀 **Автоматический мониторинг запущен!**\n\n"
        "🔍 Проверка цен каждые 30 минут\n"
        "📱 Уведомления при изменении цен\n"
        "⚡ Мгновенные уведомления о скидках"
    )

def main():
    """Основная функция программы"""
    global data
    # Инициализация
    data = load_existing_data()
    try:
        # Получение ссылки
        result = input_link()
        
        if isinstance(result, tuple):
            url, is_saved = result
        else:
            url, is_saved = result, False
        
        # Настройка заголовков
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Запрос к сайту
        response = req.get(url, headers=headers)
        soup = bs(response.text, 'html.parser')
        
        # Получение информации о товаре
        products_name, products_link = get_product_info(soup)
        
        if products_name and products_link:
            print(f"📦 Товар: {products_name}")
            
            # Получение цены
            price_info = get_price_info(soup)
            print(f"💰 Цена {price_info}") 
            
            
            # Сохранение данных только для новых товаров
            if not is_saved:
                save_product_data(products_name, products_link)
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    print("🤖 Бот запущен!")
    
    # Автоматически запускаем мониторинг
    start_monitoring()
    
    # Запускаем бота
    bot.polling()


