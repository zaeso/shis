from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
from math import floor, ceil
import numpy as np

bot = TeleBot(API_TOKEN)

manager = DatabaseManager(DATABASE)
manager.create_tables()

# Обработка входящих сообщений
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! Тебя успешно зарегистрировали! 
        Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить! 
        Для этого нужно быстрее всех нажать на кнопку 'Получить!' 
        Только три первых пользователя получат картинку!""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating()
    res = [f'| @{x[0]:<11} | {x[1]:<11} | {x[2]:<11} |\n{"_"*36}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME |COUNT_PRIZE| BALANCE|\n{"_"*36}\n' + res
    bot.send_message(message.chat.id, res)

@bot.message_handler(commands=['get_my_score'])
def handle_get_my_score(message):
    user_id = message.chat.id
    info = manager.get_winners_img(user_id)
    prizes = [x[0] for x in info]
    image_paths = os.listdir('img')
    image_paths = [f'img/{x}' if x in prizes else f'hidden_img/{x}' for x in image_paths]
    collage = create_collage(image_paths)
    cv2.imwrite('collage.jpg', collage)
    with open('collage.jpg', 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Твои достижения:")
    os.remove('collage.jpg')

@bot.message_handler(commands=['balance'])
def handle_balance(message):
    user_id = message.chat.id
    balance = manager.get_user_balance(user_id)
    bot.send_message(message.chat.id, f"Твой баланс: {balance}")

@bot.message_handler(commands=['buy_prize'])
def handle_buy_prize(message):
    user_id = message.chat.id
    balance = manager.get_user_balance(user_id)
    if balance >= PRIZE_COST:
        prize_id = manager.get_random_prize()[0]
        img = manager.get_prize_img(prize_id)
        manager.decrease_user_balance(user_id, PRIZE_COST)
        with open(f'img/{img}', 'rb') as photo:
            bot.send_photo(user_id, photo, caption="Поздравляем! Ты купил картинку!")
    else:
        bot.send_message(user_id, "Недостаточно средств. Пополните баланс!")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.chat.id
    if user_id in ADMINS:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Добавить картинку'))
        keyboard.add(KeyboardButton('Настройки'))
        bot.send_message(message.chat.id, 'Добро пожаловать, админ!', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "У вас нет прав администратора")

@bot.message_handler(func=lambda message: message.text == 'Добавить картинку' and message.chat.id in ADMINS)
def add_prize_img(message):
    bot.send_message(message.chat.id, "Отправьте картинку!")
    bot.register_next_step_handler(message, save_prize_img)

def save_prize_img(message):
    user_id = message.chat.id
    if message.photo:
        file_id = message.photo[-1].file_id
        file = bot.get_file(file_id)
        downloaded_file = bot.download_file(file.file_path)
        with open(f'img/{file.file_path.split('/')[-1]}', 'wb') as new_file:
            new_file.write(downloaded_file)
        manager.add_prize([(file.file_path.split('/')[-1],)])
        bot.send_message(user_id, "Картинка успешно добавлена!")
    else:
        bot.send_message(user_id, "Это не картинка!")

@bot.message_handler(func=lambda message: message.text == 'Настройки' and message.chat.id in ADMINS)
def handle_settings(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Периодичность отправки'))
    keyboard.add(KeyboardButton('Количество премиальных бонусов'))
    keyboard.add(KeyboardButton('Вернуться в главное меню'))
    bot.send_message(message.chat.id, 'Настройки бота:', reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Периодичность отправки' and message.chat.id in ADMINS)
def handle_send_frequency(message):
    bot.send_message(message.chat.id, 'Введите новую периодичность отправки картинок в минутах:')
    bot.register_next_step_handler(message, save_send_frequency)

def save_send_frequency(message):
    user_id = message.chat.id
    try:
        new_frequency = int(message.text)
        if new_frequency > 0:
            schedule.every(new_frequency).minutes.do(send_message)
            bot.send_message(user_id, f'Периодичность отправки изменена на {new_frequency} минут.')
        else:
            bot.send_message(user_id, 'Периодичность должна быть больше 0.')
    except ValueError:
        bot.send_message(user_id, 'Некорректное значение.')

@bot.message_handler(func=lambda message: message.text == 'Количество премиальных бонусов' and message.chat.id in ADMINS)
def handle_bonus_count(message):
    bot.send_message(message.chat.id, 'Введите новое количество премиальных бонусов:')
    bot.register_next_step_handler(message, save_bonus_count)

def save_bonus_count(message):
    user_id = message.chat.id
    try:
        new_count = int(message.text)
        if new_count > 0:
            global BONUS_COUNT
            BONUS_COUNT = new_count
            bot.send_message(user_id, f'Количество премиальных бонусов изменено на {new_count}.')
        else:
            bot.send_message(user_id, 'Количество бонусов должно быть больше 0.')
    except ValueError:
        bot.send_message(user_id, 'Некорректное значение.')

@bot.message_handler(func=lambda message: message.text == 'Вернуться в главное меню' and message.chat.id in ADMINS)
def handle_back_to_main(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Добавить картинку'))
    keyboard.add(KeyboardButton('Настройки'))
    bot.send_message(message.chat.id, 'Админ меню:', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.message.chat.id
    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            manager.increase_user_balance(user_id, PRIZE_COST)
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!")

def send_message():
    prize_id, img = manager.get_random_prize()[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id=prize_id))

def shedule_thread():
    schedule.every().minute.do(send_message)
    while True:
        schedule.run_pending()
        time.sleep(1)

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    # Запуск потоков для бота и расписания
    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)
    polling_thread.start()
    polling_shedule.start()