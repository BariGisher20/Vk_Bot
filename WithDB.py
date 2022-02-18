import vk_api
import requests
import sqlite3
import time
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from config import my_token, bot_token



# создание кнопок
keyboard = VkKeyboard(inline=False)
keyboard.add_button('Стоп', color=VkKeyboardColor('secondary'))
keyboard.add_button('Начать', color=VkKeyboardColor('primary'))
keyboard.add_button('Продолжить', color=VkKeyboardColor('positive'))
# авторизация вк
vk_session = vk_api.VkApi(token=bot_token)
session = vk_session.get_api()
longpool = VkLongPoll(vk_session)
# подключение БД
db = sqlite3.connect('Vk_Bot.db')
sql = db.cursor()
# создание БД под юзера, который пишет нам
sql.execute("""CREATE TABLE IF NOT EXISTS users (
    userId BIGINT,
    act TEXT,
    city INT,
    gender INT,
    age_from INT,
    age_to INT
    )""")
db.commit()
userAct = '0'


def get_info(user_id):
    url_match_to = 'https://api.vk.com/method/users.get'
    params_match_to = {
        'access_token': my_token,
        'user_ids': user_id,
        'fields': 'sex, city, relation',
        'v':  '5.81'
    }
    res_my_info = requests.get(url=url_match_to, params=params_match_to)
    event_user_info = res_my_info.json().get('response')
    return event_user_info


def find_users_match():
    url_search = 'https://api.vk.com/method/users.search'
    for info in get_info(user_id):
        if info.get('sex') == 1:
            info['sex'] = 2
        elif info.get('sex') == 2:
            info['sex'] = 1
        if info.get('city').get('id') == 1:
            info['city'] = 1
        params_search = {
            'access_token': my_token,
            'city': info['city'],
            'sex': info['sex'],
            'relation': int(info.get('relation')),
            'age_from': sql.execute((f"""
                SELECT age_from FROM users WHERE userid = '{user_id}'""")).fetchone(),
            'age_to': sql.execute((f"""
                SELECT age_to FROM users WHERE userid = '{user_id}'""")).fetchone(),
            'fields': 'sex, city, relation',
            'v':  '5.81'
        }
        res_search = requests.get(url=url_search, params=params_search)
        response = res_search.json().get('response')
        return response.get('items')


def get_photo(list):
    url_get_match_users_photos = 'https://api.vk.com/method/photos.get'
    for user_info in find_users_match():
        params_vk = {
            'access_token': my_token,
            'owner_id': user_info.get('id'),
            'album_id': 'profile',
            'extended': 1,
            'photo_sizes': 1,
            'v': '5.81'
        }
        img = requests.get(url=url_get_match_users_photos, params=params_vk).json()
        response = img.get('response')
        users_photo = {}
        photos = []
        users_likes = []
        time.sleep(1)
        if 'error' not in img.keys():
            if response.get('count') != 0:
                for ids in response.get('items'):
                    if response.get('items') is not None:
                        photos.append(ids.get('id'))
                        users_likes.append(ids.get('likes').get('count'))
                        users_photo.update(owner_id=(ids.get('owner_id')), photo_info=dict(zip(photos, users_likes)))
                    photo_info = users_photo.get('photo_info')
                    sorted_photo_info = dict(sorted(photo_info.items(), key=lambda x: x[1])[-3:])
                    users_photo.update(photo_info=sorted_photo_info)
                yield users_photo


def send_message(user_id, message):
    vk_session.method('messages.send', {
        'user_id': user_id,
        'message': message,
        'random_id': get_random_id(),
        'attachment': ','.join(attachments),
        'keyboard': keyboard.get_keyboard()
        })


def info_in_message():
    for i in get_photo(find_users_match()):
        user_link = 'vk.com/id' + str(i.get('owner_id'))
        photo_ids = list(i['photo_info'].keys())
        for el in photo_ids:
            attachments.extend((user_link, 'photo{}_{}'.format(i['owner_id'], el)))
        for photo in attachments:
            yield photo


def fix_message(msg):
    msg = "'"+msg+"'"
    return msg


for event in longpool.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        msg = event.text.lower()
        user_id = event.user_id  # тот, кому мы пишем сообщение
        users_acts = {
            user_id: [userAct]
        }
        attachments = []
        sql.execute(f"SELECT userId FROM users WHERE userId = '{user_id}'")
        if sql.fetchone() is None:  # если записи о пользователе нет
            sql.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (user_id, "newUser", "0", "0", "0", "0"))
            db.commit()
            send_message(user_id, "Привет, напиши 'начать', что бы запустить поиск")
        else:
            userAct = sql.execute(f"SELECT act FROM users WHERE userId = '{user_id}'").fetchone()[0]
            if userAct == "newUser" and msg == "начать":
                send_message(user_id, "Ой, кажется, ты не зарегистрирован! Отправь 'рег' для регистрации.")
            elif userAct == "newUser" and msg == "рег":
                sql.execute(f"UPDATE users SET act = 'getCity' WHERE userId = {user_id}")
                db.commit()
                send_message(user_id, "Не хватает информации о городе! В каком городе проведем поиск?")
            elif userAct == "getCity":
                sql.execute(f"UPDATE users SET city = {fix_message(msg)} WHERE userId = {user_id}")  # подставляем в соотв. ячейку значение, присланное пользователем
                sql.execute(f"UPDATE users SET act = 'getGender' WHERE userId = {user_id}")  # спрашиваем следующую инфу
                users_acts[user_id].append(userAct)
                db.commit()
                send_message(user_id, "Твой пол?")
            elif userAct == "getGender":
                sql.execute(f"UPDATE users SET gender = {fix_message(msg)} WHERE userId = {user_id}")
                sql.execute(f"UPDATE users SET act = 'getAgeFrom' WHERE userId = {user_id}")
                db.commit()
                send_message(user_id, "От какого возраста ищем друга?")
            elif userAct == "getAgeFrom":
                sql.execute(f"UPDATE users SET age_from = {fix_message(msg)} WHERE userId = {user_id}")
                sql.execute(f"UPDATE users SET act = 'getAgeTo' WHERE userId = {user_id}")
                db.commit()
                send_message(user_id, "Хм, а верхний предел?")
            elif userAct == "getAgeTo":
                sql.execute(f"UPDATE users SET age_to = {fix_message(msg)} WHERE userId = {user_id}")
                sql.execute(f"UPDATE users SET act = 'full' WHERE userId = {user_id}")
                db.commit()
                send_message(user_id, "Регистрация прошла успешно. Давай найдем тебе пару! ;) Напиши 'продолжить'")
            elif userAct == "full" and msg == "начать":
                sql.execute(f"UPDATE users SET act = 'full' WHERE userId = {user_id}")
                db.commit()
                send_message(user_id, "Не первый раз у нас? Давай искать пару. Напиши 'продолжить'")
                users_acts[user_id].append(userAct)
            elif userAct == "full" and msg == 'продолжить':
                sql.execute(f"UPDATE users SET act = 'sent_photo' WHERE userId = {user_id}")
                for k in info_in_message():
                    send_message(user_id, '{}'.format(k))
                    db.commit()
                    attachments.clear()
                    send_message(user_id, 'Продолжить поиск?')
                # time.sleep(1)
            elif userAct == "sent_photo" and msg == 'yes':
                for k in info_in_message():
                    # проблема в этом цикле, он ведь итерируется по нему до конца, не ожидая сообщения.
                    # Ожидает только в случае, если в функции info_in_message() ставлю return,
                    # но в таком случае, он просто не рассматривает тех, кто после первого идет (что логично, по фунции return)
                    sql.execute(f"UPDATE users SET act = 'want_more' WHERE userId = {user_id}")
                    users_acts[user_id].append(userAct)
                    db.commit()
                    send_message(user_id, '{}'.format(k))
            elif userAct == "sent_photo" and msg == 'стоп':
                sql.execute(f"UPDATE users SET act = 'dont_want_more' WHERE userId = {user_id}")
                users_acts[user_id].append(userAct)
                db.commit()
                send_message(user_id, 'Ждем Вас снова!')
                raise StopIteration



