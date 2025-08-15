import subprocess
import sys
import json
import os
import psutil
from pathlib import Path

# Глобальная переменная для хранения процесса бота
bot_process = None

def start_bot():
    """Запускает бота"""
    global bot_process
    
    # Проверяем, не запущен ли уже бот
    if is_bot_running():
        print("⚠️ Бот уже запущен!")
        return
    
    bot_path = Path(__file__).parent / "telegram_bot.py"
    bot_process = subprocess.Popen([sys.executable, str(bot_path)])
    print("✅ Бот запущен!")

def stop_bot():
    """Останавливает бота"""
    global bot_process
    
    stopped_count = 0
    
    # Останавливаем процесс, запущенный через панель
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process = None
        stopped_count += 1
    
    # Ищем и останавливаем все процессы связанные с ботом
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Ищем процессы Python с telegram_bot.py
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'telegram_bot.py' in cmdline:
                    proc.terminate()
                    stopped_count += 1
            
            # Ищем процессы silpo.exe
            if 'silpo.exe' in proc.info['name'].lower():
                proc.terminate()
                stopped_count += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if stopped_count > 0:
        print(f"⏹️ Остановлено {stopped_count} процесс(ов)!")
    else:
        print("ℹ️ Активные процессы бота не найдены!")

def is_bot_running():
    """Проверяет, запущен ли бот"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'telegram_bot.py' in cmdline:
                    return True
            if 'silpo.exe' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def show_products():
    """Показывает товары"""
    try:
        with open('products_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("\n📦 ТОВАРЫ:")
        for i, product in enumerate(data['products'], 1):
            print(f"{i}. {product}")
        print(f"\nВсего товаров: {data['count']}")
    except:
        print("❌ Файл товаров не найден!")

def main():
    while True:
        os.system('cls')
        print("🤖 SILPO BOT CONTROL PANEL")
        print("=" * 30)
        
        # Показываем статус бота
        if is_bot_running():
            print("🟢 Статус: БОТ ЗАПУЩЕН")
        else:
            print("🔴 Статус: БОТ ОСТАНОВЛЕН")
        
        print("\n1. ▶️ Запустить бота")
        print("2. ⏹️ Остановить бота") 
        print("3. 📦 Показать товары")
        print("4. 🚪 Выход")
        
        choice = input("\n👉 Выбор: ")
        
        if choice == "1":
            start_bot()
        elif choice == "2":
            stop_bot()
        elif choice == "3":
            show_products()
        elif choice == "4":
            break
        else:
            print("❌ Неверный выбор!")
            
        input("\n⏳ Нажмите Enter...")

if __name__ == "__main__":
    main()
