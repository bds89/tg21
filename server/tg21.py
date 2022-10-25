import time, os, platform, sys, inspect, logging, yaml, re, sqlite3, asyncio, datetime, apscheduler, calendar
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
from telegram.error import BadRequest
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CallbackContext,
)
from modbus_crc16 import crc16
from set4tm_const import *
SLASH = "/"


class User:
    def __init__(self, id, name="?", surname="?", auth="GUEST", tryn=0, notify=0):
        self.id = id
        self.name = name
        self.surname = surname
        self.auth = auth
        self.tryn = tryn
        self.notify = notify

    def save_to_db(self, params=[]):
        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()
        user = (self.id, self.name, self.surname, self.auth, self.tryn, self.notify)
        if not params:
            try:
                cursor.execute('''SELECT id FROM users WHERE id = ?''', (self.id,))
                if not cursor.fetchall(): 
                    cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                else:
                    cursor.execute('''UPDATE users 
                                        SET name = ?,
                                        surname = ?,
                                        auth = ?,
                                        tryn = ?,
                                        notify = ?
                                            where id = ?''', (self.name, self.surname, self.auth, self.tryn, self.notify, self.id))
                sqlite_connection.commit()
                sqlite_connection.close()
                return True
            except Exception as e:
                logger.error("Exception: "+str(e)+" in save to DB users without params")
                logger.info((self.name, self.surname, self.auth, self.tryn, self.notify, self.id))
                return False
        else:
            try:
                new_user = False
                cursor.execute('''SELECT id FROM users WHERE id = ?''', (self.id,))
                if not cursor.fetchall(): new_user = True
                if "name" in params:
                    if new_user: 
                        cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                        new_user = False
                    else: cursor.execute('''UPDATE users SET name = ? where id = ?''', (self.name, self.id))
                if "surname" in params:
                    if new_user: 
                        cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                        new_user = False
                    else: cursor.execute('''UPDATE users SET surname = ? where id = ?''', (self.surname, self.id))
                if "auth" in params:
                    if new_user: 
                        cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                        new_user = False
                    else: cursor.execute('''UPDATE users SET auth = ? where id = ?''', (self.auth, self.id))
                if "tryn" in params:
                    if new_user: 
                        cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                        new_user = False
                    else: cursor.execute('''UPDATE users SET tryn = ? where id = ?''', (self.tryn, self.id))
                if "notify" in params:
                    if new_user: 
                        cursor.execute('''INSERT INTO users VALUES(?,?,?,?,?,?)''', user)
                        new_user = False
                    else: cursor.execute('''UPDATE users SET notify = ? where id = ?''', (self.notify, self.id))
                sqlite_connection.commit()
                sqlite_connection.close()
                return True
            except Exception as e:
                logger.error("Exception: "+str(e)+" in save to DB users with params:"+params)
                logger.info((self.name, self.surname, self.auth, self.tryn, self.notify, self.id))
                return False

    def load_from_db(self, param=""):
        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()

        if not param:
            users = []
            try:
                cursor.execute('''SELECT * FROM users WHERE id = ? ''', (self.id,))
                user = cursor.fetchone()
                sqlite_connection.close()
            except Exception as e:
                logger.error("Exception: "+str(e)+" in load from DB without params")
                return False
            if user:
                self.id = user[0]
                self.name = user[1]
                self.surname = user[2]
                self.auth = user[3]
                self.tryn = user[4]
                self.notify = user[5]
                sqlite_connection.close()
                return True
            else: 
                sqlite_connection.close()
                return False

        try:
            cursor.execute('''SELECT ? FROM users WHERE id = ? ''', (param, self.id))
            user = cursor.fetchone()
            sqlite_connection.close()
        except Exception as e:
            logger.error("Exception: "+str(e)+" in load from DB users with param:"+param)
            return False
        if user:
            if param == "name": self.name = user[0]
            if param == "surname": self.surname = user[0]
            if param == "auth": self.auth = user[0]
            if param == "tryn": self.tryn = user[0]
            if param == "notify": self.notify = user[0]
            sqlite_connection.close()
            return user[0]
        else: 
            sqlite_connection.close()
            return False

    def delete_from_db(self, id):
        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()

        try:
            cursor.execute('''DELETE FROM users WHERE id = ? ''', (id,))
            sqlite_connection.commit()
        except Exception as e:
            logger.error("Exception: "+str(e)+" in delete from DB users")
            sqlite_connection.close()
            return False
        sqlite_connection.close()
        return True

def load_all_users(filter=[]): 
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    retur = []
    users = []
    try:
        if filter:
            request = f"SELECT * FROM users WHERE {filter[0]} = {filter[1]}"
        else:
            request = '''SELECT * FROM users'''
        cursor.execute(request)
        users = cursor.fetchall()
    except Exception as e:
        logger.error("Exception: "+str(e)+" in load from DB all users")
        return retur
    finally: sqlite_connection.close()
    if users:
        for user in users:
            retur.append(User(user[0], user[1], user[2], user[3], user[4], user[5]))
    return retur

async def save_energy_to_db():
    try_n = 0
    while (try_n < 5):
        REQUESTS.update({0 : "DataBase update"})
        start_time = time.time()
        address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')
        tarif = (1).to_bytes(1, byteorder='big')
        request = address+b'\x05\x00'+tarif
        lo, hi  = crc16(request)
        request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
        request += access_request(address)

        responce = await queue_tx_put(request+EOF, False)

        #check responce
        if type(responce) == str:
            try_n += 1
            await asyncio.sleep(60)
            REQUESTS.pop(0, 1)
            continue
        else:
            if len(responce) < 19:
                try_n += 1
                await asyncio.sleep(60)
                REQUESTS.pop(0, 1)
                continue
            else:
                A = CONFIG["DEVICE_A"]
                a_plus, a_minus, r_plus, r_minus = energy_to_kwt(responce, A)
                k = eval(CONFIG["DEVICE_Ktt"])*eval(CONFIG["DEVICE_Ktn"])
                data = a_plus*k
                globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
                break

    REQUESTS.pop(0, 1)
    if "data" in locals():
        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()
        try:
            cursor.execute('''INSERT INTO active_energy VALUES(?,?)''', (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data))
            sqlite_connection.commit()
        except Exception as e:
            logger.error("Exception: "+str(e)+" in save to DB active_energy")
        finally:
            sqlite_connection.close()

async def delete_energy_from_db():
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("DELETE FROM active_energy WHERE date < DATE('"+year_ago+"')")
        sqlite_connection.commit()
    except Exception as e:
        logger.error("Exception: "+str(e)+" in save to DB active_energy")
    finally:
        sqlite_connection.close()


def num_to_scale(percent_value, numsimb, add_percent=True, prefix="", value="", si=""):
    output_text = ""
    if percent_value > 100: percent_value_scale = 100
    else: percent_value_scale = percent_value
    scale = "<s>"
    blocks = ["⠀", "▏", "▎", "▍", "▌", "▋", "▊", "█"]
    discretization = numsimb*7
    simbols = (percent_value_scale/100) * discretization
    full_simbols = int(simbols // 7)
    half_simbol = int(simbols % 7)
    for i in range(full_simbols):
        scale += blocks[7]
    if percent_value_scale != 100:
        scale += blocks[half_simbol]
    for i in range(numsimb-full_simbols-1):
        if i == 0 and full_simbols == 0 and half_simbol == 0: 
            scale = "<s>▏⠀"
            continue
        scale += blocks[0]

    scale += "</s>▏"
    if type(value) != str:
        k_letter = 180/267
        k_point = 112/267
        k_space = 104/267
        text = str(value) +" "+ si
        start_pos = ((len(scale))\
                    -(((len(text)-text.count('.')+text.count(' '))*k_letter)\
                    +text.count('.')*k_point+text.count(' ')*k_space))/2
        for i in range(int(round(start_pos))):
            output_text += "⠀"
        output_text += text + "\n"
    if add_percent:
        scale += " "+str(round(percent_value))+'%'
    if prefix:
        scale = prefix +scale
    output_text += scale
    return(output_text)

def num_to_scale2(value, min, max, numsimb, add_value=True, prefix="", si=""):
    if numsimb % 2 == 1:
        numsimb -= 1
    output_text = ""
    
    blocks = ["⠀", "|", "▌"]

    current_value = round(((value - min)/(max - min))*numsimb)
    if current_value > numsimb: current_value = numsimb-1
    if current_value <= 0: 
        scale = "<s>"
        current_value = 0
    else: scale = "<s>▏"
    for i in range(numsimb):
        if i == current_value:
            scale += blocks[2]
            continue
        elif i == int((numsimb/2)):
            scale += blocks[1]
            continue
        else: scale += blocks[0]

    scale += "</s>▏"
    if value:
        k_letter = 180/267
        k_point = 112/267
        k_space = 104/267
        text = str(value) +" "+ si
        start_pos = ((len(scale))\
                    -(((len(text)-text.count('.')+text.count(' '))*k_letter)\
                    +text.count('.')*k_point+text.count(' ')*k_space))/2
        for i in range(int(round(start_pos))):
            output_text += "⠀"
        output_text += text + "\n"
    if prefix:
        scale = prefix +scale
    output_text += scale
    return(output_text)

def signal_to_scale(rssi):
    try:
        signal = int(rssi)
        signal = (signal * 2) - 113
        if signal < -109: signal_str = "RSSI: "+str(rssi) +" (📡: ▂    )"
        if signal < -95 and signal >= -109: signal_str = "RSSI: "+str(rssi) +" (📡: ▂▃   )"
        if signal < -85 and signal >= -95: signal_str = "RSSI: "+str(rssi) +" (📡: ▂▃▅  )"
        if signal < -75 and signal >= -85: signal_str = "RSSI: "+str(rssi) +" (📡: ▂▃▅▇ )"
        if signal >= -75: signal_str = "RSSI: "+str(rssi) +" (📡: ▂▃▅▇█)"
    except Exception:
        signal_str = 'RSSI: unknown'
    finally:
        return signal_str

def check_system():
    system = platform.system()
    if system == "Windows":
        globals()["SYSTEM"] = "Windows"
        return "\\"
    else: 
        globals()["SYSTEM"] = "Linux"
        return "/"

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

       


AUTH, MAIN, FOTA, SETTINGS, STAT = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message: u = update.message.from_user
    else: u = update.callback_query.from_user
    user = User(id=u.id)
    if user.load_from_db(): 
        context.user_data["user"] = user
    else: 
        user.auth = "GUEST"
        user.name = u.first_name
        user.surname = u.last_name

    if user.auth == "BLACK": return ConversationHandler.END

    if user.auth == "USER" or user.auth == "ADMIN":
        await main_menu(update, context)
        return MAIN

    context.user_data["user"] = user
    if update.message:
        context.chat_data["last_message"] = await update.message.reply_text(
            "🔐 Please enter your password",
        )
    else:
        await update.callback_query.answer()
        context.chat_data["last_message"] = await update.callback_query.message.reply_text(
            "🔐 Please enter your password",
        )
    return AUTH

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        user = update.message.from_user
        user_pass = update.message.text
        if user_pass == str(CONFIG["PASSWORD"]) or ("ADMIN_PASSWORD" in CONFIG and user_pass == str(CONFIG["ADMIN_PASSWORD"])):
            if user_pass == str(CONFIG["PASSWORD"]):
                context.user_data["user"].auth = "USER"
            if "ADMIN_PASSWORD" in CONFIG and user_pass == str(CONFIG["ADMIN_PASSWORD"]):
                context.user_data["user"].auth = "ADMIN"
            context.user_data["user"].name = user.first_name
            context.user_data["user"].surname = user.last_name
            context.user_data["user"].tryn = 0
            context.user_data["user"].save_to_db()
            mess = "User "+str(user.first_name)+" "+str(user.last_name)+": "+str(user.id)+" successfully logged in"
            logger.info(mess)
            await send_simple_message(mess, True)
            await main_menu(update, context)
            return MAIN
    
        else:
            mess = "User "+str(user.first_name)+" "+str(user.last_name)+": "+str(user.id)+" type wrong password: "+user_pass
            logger.warning(mess)
            context.user_data["user"].tryn += 1
            await send_simple_message(mess, True)
            
            if context.user_data["user"].tryn > 4:
                context.user_data["user"].auth = "BLACK"
                context.user_data["user"].name = user.first_name
                context.user_data["user"].surname = user.last_name
                context.user_data["user"].save_to_db()

                mess = "User "+str(user.first_name)+" "+str(user.last_name)+": "+str(user.id)+" was banned"
                logger.warning(mess)
                await send_simple_message(mess, True)

                return ConversationHandler.END
            
            else: 
                context.user_data["user"].save_to_db()

            context.chat_data["last_message"] = await update.message.reply_text(
                "⛔ Password is incorrect, please try again"
            )
            return AUTH
    else: return AUTH

def chop_microseconds(delta):
    return delta - datetime.timedelta(microseconds=delta.microseconds)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("Энергия", callback_data="energy"),
            InlineKeyboardButton("Статистика", callback_data="stat"),],
    )
    keyboard.append(
        [
            InlineKeyboardButton("➕ Дополнительно", callback_data="dop"),
            InlineKeyboardButton("⚙ Настройки", callback_data="settings"),
        ]
    )
    text = "Номер счетчика: 0818174046\n"+device_status+"\n"\
            +"Время отклика: "+last_time_responce+"\n"\
            +"UP time: "+str(chop_microseconds(datetime.datetime.now()-start_time))

    if update.message:
        context.chat_data["last_message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        if update.callback_query.message.text != text and update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
            await update.callback_query.answer()
            context.chat_data["last_message"] = await update.callback_query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
        else: await update.callback_query.answer()
    return MAIN

async def fota_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("🏠", callback_data="home")
        ]
    )
    if context.user_data["user"].auth == "ADMIN":
        text = "FOTA:\nПришлите скомпилированный *.pyo файл размером не более 16 КБ"
    else:
        text = "FOTA:\nОбновление прошивки устройства доступно только администраторам"
        keyboard[0].append(InlineKeyboardButton("Авторизация", callback_data="logout"))
    
    context.chat_data["last_message"] = await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )

    if context.user_data["user"].auth == "ADMIN": return FOTA
    else: return MAIN

    

async def fota_send_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    text = "FOTA:\n"
    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("🏠", callback_data="home")
        ]
    ) 


    
    file = await update.message.document.get_file()
    byte_file = await file.download_as_bytearray()
    file_length = len(byte_file)
    if file_length < 16000:
        if len(REQUESTS) > 0:
            text+="\n"
            text+=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...'
            REQUESTS.update({update.message.from_user.id : update.message.from_user.full_name})
        else:
            text += num_to_scale(0, 16)
            REQUESTS.update({update.message.from_user.id : update.message.from_user.full_name})

        context.chat_data["last_message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

        text = "FOTA:\n"

        responce = await queue_tx_put(FOTA+str(file_length).encode()+EOF, True)
        #check responce
        if type(responce) == str:
            text += responce
        elif FOTA in responce:
            pkt_size = int(responce[len(FOTA):])
            logger.info("pkt_size:"+str(pkt_size))
            sended = 0
            start_time = time.time()
            while(sended < file_length):
                delta_t = time.time()-start_time
                if delta_t == 0: speed = "0 kbit/s"
                else: speed = str(round((pkt_size/delta_t)*8*0.0009765625, 2))+" kbit/s"
                start_time = time.time()
                to = sended+pkt_size
                if to > file_length: to = file_length
                file_part = byte_file[sended:to]
                responce = await queue_tx_put(file_part, False)
                if type(responce) == str:
                    text += responce
                    break
                else:
                    if not FOTA in responce:
                        text = "FOTA:\n"+responce[len[b'responce']:responce.find(b'%edn%')].decode()        
                    else:
                        sended = int(responce[len(FOTA):].decode())
                        text = "FOTA:\n"+num_to_scale(round((sended/file_length)*100), 16)+"\n"+speed
                    try:
                        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
                            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                        )
                    except BadRequest: pass
            if responce and type(responce) != str:
                responce = await queue_tx_put(APPLY+EOF, False)
            if type(responce) == str:
                text = "FOTA:\n"+responce
            else: text = "FOTA:\n"+responce.decode()
        else:
            text += "Unknown error"

        REQUESTS.pop(update.message.from_user.id, 1)
    else:
        text += "Превышен допустимый размер файла. Ваш файл: "+str(file_length)+" байт"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    return MAIN

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("🏠", callback_data="home")
        ]
    ) 

    if context.user_data["user"].auth == "ADMIN":
        start_time = time.time()
        text = "Reboot:\nВыполняю..."
        if len(REQUESTS) > 0:
            await update.message.reply_text(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
            REQUESTS.update({update.message.from_user.id : update.message.from_user.full_name})
        else:
            REQUESTS.update({update.message.from_user.id : update.message.from_user.full_name})

        context.chat_data["last_message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )

        text = "Reboot:\n"
        responce = await queue_tx_put(RESTART+EOF, False)
        #check responce
        if type(responce) == str:
            text += responce
        elif RESTART in responce:
            text = responce.decode()
        else:
            text += "Unknown error"

        globals()["last_time_responce"] = str(round(time.time()-start_time, 2))+" c"
    else:
        text = "Reboot:\nПерезагрузка устройства доступна только администраторам"
        keyboard[0].append(InlineKeyboardButton("Авторизация", callback_data="logout"))

    REQUESTS.pop(update.message.from_user.id, 1)
    context.chat_data["last_message"] = await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )    
    return MAIN

async def energy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("🏠", callback_data="home"),
            InlineKeyboardButton("Обновить", callback_data="energy"),
        ]
    )
    
    text = "Показания электроэнергии:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass

    text = "Показания электроэнергии:\n\n"
    start_time = time.time()
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')
    tarif = (1).to_bytes(1, byteorder='big')
    request = address+b'\x05\x00'+tarif
    lo, hi  = crc16(request)
    request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
    request += access_request(address)

    responce = await queue_tx_put(request+EOF, False)
    
    #check responce
    if type(responce) == str:
        text += responce +'\nПопробуйте отправить сообщение с текстом "Energy" на номер: '+CONFIG["SIM_PHONE"]
    else:
        if len(responce) < 19:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text += f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
            text +='\nПопробуйте отправить сообщение с текстом "Energy" на номер: '+CONFIG["SIM_PHONE"]
        else:
            A = CONFIG["DEVICE_A"]
            a_plus, a_minus, r_plus, r_minus = energy_to_kwt(responce, A)
            text += '<b>Активная прямая: <u>{0}</u> кВт*ч</b>\nАктивная обратная: {1} кВт*ч\nРеактивная прямая: {2} квар*ч\nРеактивная обратная: {3} квар*ч'.format(
                round(a_plus,2), round(a_minus,2), round(r_plus,2), round(r_minus,2)
            )
            k = eval(CONFIG["DEVICE_Ktt"])*eval(CONFIG["DEVICE_Ktn"])
            text += '\n\nС учетом коэффициентов трансформации:\n\nАктивная прямая: {0} кВт*ч\nАктивная обратная: {1} кВт*ч\nРеактивная прямая: {2} квар*ч\nРеактивная обратная: {3} квар*ч'.format(
                round(a_plus*k), round(a_minus*k), round(r_plus*k), round(r_minus*k)
            )
    globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"

    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

async def power(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
                [InlineKeyboardButton("Обновить", callback_data="power"),
                InlineKeyboardButton("Напряжение", callback_data="voltage"),
                InlineKeyboardButton("Ток", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Частота", callback_data="freq"),
                InlineKeyboardButton("Температура", callback_data="temperature")],
                ]
    
    text = "Мгновенная мощность:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
        
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass
    start_time = time.time()
    text = "Мгновенная мощность:\n\n"
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')

    power_dict = {}
    triple_request = TRIPLE
    for key, value in BITS_PARAMS.items():
        request = address+b'\x08\x11'
        if key == 'P' or key == 'Q' or key == 'S':
            request += int(value, 2).to_bytes(1, byteorder='big')
            lo, hi  = crc16(request)
            request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
            triple_request += request

    triple_request += access_request(address)
    responce = await queue_tx_put(triple_request+EOF, False)
    #check responce
    if type(responce) == str:
        text = "Мгновенная мощность:\n\n" + responce
    else:
        if len(responce) != 6*3:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text = "Мгновенная мощность:\n\n" + f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
        else:
            responce_list = [responce[0:6], responce[6:12], responce[12:18]]
            i = 0
            for responce in responce_list:
                i += 1
                mask_byte = responce[1:2]
                bits = bin(int.from_bytes(mask_byte, "big"))[4:]
                byte = int(bits, 2).to_bytes(1, byteorder='big')
                geted_value = (int.from_bytes((byte+responce[2:4]), "big")/1000000)*CONFIG["DEVICE_Kc"]*eval(CONFIG["DEVICE_Ktt"])*eval(CONFIG["DEVICE_Ktn"])
                if i == 1: power_dict.update({"P: ":round(geted_value,3)})
                elif i == 2: power_dict.update({"Q: ":round(geted_value,3)})
                else: power_dict.update({"S: ":round(geted_value,3)})

    power_dict.update({"\ncosφ: ":round(power_dict["P: "]/power_dict["S: "],2)})
    
    S_full_scale = int(CONFIG["DEVICE_Ktt"][:CONFIG["DEVICE_Ktt"].find("/")])*int(CONFIG["DEVICE_Ktn"][:CONFIG["DEVICE_Ktn"].find("/")])*0.003
    for key, value in power_dict.items():
        if key == "\ncosφ: ": break
        if key == "P: ":
            fs = S_full_scale*power_dict["\ncosφ: "]
            si = " кВт"
        elif key == "P: ":
            fs = S_full_scale*(1-power_dict["\ncosφ: "])
            si = " квар"
        else:
            fs = S_full_scale*power_dict["\ncosφ: "]
            si = " кВА"
        text += num_to_scale((value/fs)*100,16,add_percent=True, prefix=key, value=value, si=si)+"\n"
    text += "\ncosφ: "+str(power_dict["\ncosφ: "])
    
    globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

async def voltage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
                [InlineKeyboardButton("Мощность", callback_data="power"),
                InlineKeyboardButton("Обновить", callback_data="voltage"),
                InlineKeyboardButton("Ток", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Частота", callback_data="freq"),
                InlineKeyboardButton("Температура", callback_data="temperature")],
                ]
    
    text = "Значения напряжений:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
        
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass
    start_time = time.time()
    text = "Значения напряжений:\n\n"
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')

    triple_request = TRIPLE
    for key, value in BITS_PARAMS.items():
        request = address+b'\x08\x11'
        if key == 'U1' or key == 'U2' or key == 'U3':
            request += int(value, 2).to_bytes(1, byteorder='big')
            lo, hi  = crc16(request)
            request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
            triple_request += request

    triple_request += access_request(address)
    responce = await queue_tx_put(triple_request+EOF, False)
    #check responce
    if type(responce) == str:
        text = "Значения напряжений:\n\n" + responce
    else:
        if len(responce) != 6*3:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text = "Значения напряжений:\n\n" + f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
        else:
            responce_list = [responce[0:6], responce[6:12], responce[12:18]]
            i = 0
            for responce in responce_list:
                i += 1
                mask_byte = responce[1:2]
                bits = bin(int.from_bytes(mask_byte, "big"))[4:]
                byte = int(bits, 2).to_bytes(1, byteorder='big')
                geted_value = (int.from_bytes((byte+responce[2:4]), "big")/100)*eval(CONFIG["DEVICE_Ktn"])
                si = " В"
                if i == 1:   
                    key = "Ua: "
                elif i == 2: 
                    key = "Ub: "
                else: 
                    key = "Uc: "
                text += num_to_scale2(round(geted_value,2), 207, 253, 18, True, key, si)+"\n"

    globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

async def current(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
                [InlineKeyboardButton("Мощность", callback_data="power"),
                InlineKeyboardButton("Напряжение", callback_data="voltage"),
                InlineKeyboardButton("Обновить", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Частота", callback_data="freq"),
                InlineKeyboardButton("Температура", callback_data="temperature")],
                ]
    
    text = "Значения токов:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
        
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass
    start_time = time.time()
    text = "Значения токов:\n\n"
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')

    current_dict = {}
    triple_request = TRIPLE
    for key, value in BITS_PARAMS.items():
        request = address+b'\x08\x11'
        if key == 'I1' or key == 'I2' or key == 'I3':
            request += int(value, 2).to_bytes(1, byteorder='big')
            lo, hi  = crc16(request)
            request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
            triple_request += request

    triple_request += access_request(address)
    responce = await queue_tx_put(triple_request+EOF, False)
    #check responce
    if type(responce) == str:
        text = "Значения токов:\n\n" + responce
    else:
        if len(responce) != 6*3:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text = "Значения токов:\n\n" + f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
        else:
            responce_list = [responce[0:6], responce[6:12], responce[12:18]]
            i = 0
            for responce in responce_list:
                i += 1
                mask_byte = responce[1:2]
                bits = bin(int.from_bytes(mask_byte, "big"))[4:]
                byte = int(bits, 2).to_bytes(1, byteorder='big')
                geted_value = int.from_bytes((byte+responce[2:4]), "big")*eval(CONFIG["DEVICE_Ktt"])/10000
                if i == 1: current_dict.update({"Ia: ":round(geted_value,3)})
                elif i == 2: current_dict.update({"Ib: ":round(geted_value,3)})
                else: current_dict.update({"Ic: ":round(geted_value,3)})

    I_full_scale = int(CONFIG["DEVICE_Ktt"][:CONFIG["DEVICE_Ktt"].find("/")])
    si = " А"
    for key, value in current_dict.items():
        text += num_to_scale((value/I_full_scale)*100,14,add_percent=True, prefix=key, value=value, si=si)+"\n"


    globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

async def freq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
                [InlineKeyboardButton("Мощность", callback_data="power"),
                InlineKeyboardButton("Напряжение", callback_data="voltage"),
                InlineKeyboardButton("Ток", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Обновить", callback_data="freq"),
                InlineKeyboardButton("Температура", callback_data="temperature")],
                ]
    
    text = "Значение частоты:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
        
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass

    text = "Значение частоты:\n\n"
    start_time = time.time()
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')

    
    request = address+b'\x08\x11'
    request += int(BITS_PARAMS["f"], 2).to_bytes(1, byteorder='big')
    lo, hi  = crc16(request)
    request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')

    request += access_request(address)
    responce = await queue_tx_put(request+EOF, False)
        #check responce
    if type(responce) == str:
        text = "Значение частоты:\n\n" + responce
    else:
        if len(responce) != 6:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text = "Значение частоты:\n\n" + f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
        else:
            mask_byte = responce[1:2]
            bits = bin(int.from_bytes(mask_byte, "big"))[4:]
            byte = int(bits, 2).to_bytes(1, byteorder='big')
            geted_value = int.from_bytes((byte+responce[2:4]), "big")/100
            si = " Гц"
            text += num_to_scale2(round(geted_value, 2), 49.8, 50.2, 18, True, "", si)+"\n"
            globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass

    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

async def temperature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
                [InlineKeyboardButton("Мощность", callback_data="power"),
                InlineKeyboardButton("Напряжение", callback_data="voltage"),
                InlineKeyboardButton("Ток", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Частота", callback_data="freq"),
                InlineKeyboardButton("Обновить", callback_data="temperature")],
                ]
    
    text = "Значение внутренней температуры счетчика:\nВыполняю..."
    if len(REQUESTS) > 0:
        await update.callback_query.answer(text=f'Канал связи с модемом занят пользователем {list(REQUESTS.values())[0]}, ваш запрос поставлен в очередь, ожидайте...', show_alert=True)
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
    else:
        REQUESTS.update({update.callback_query.from_user.id : update.callback_query.from_user.full_name})
        
    await update.callback_query.answer()
    if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
        context.chat_data["last_message"] = await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else: pass

    text = "Значение внутренней температуры счетчика:\n\n"
    start_time = time.time()
    address = CONFIG["DEVICE_ADDRESS"].to_bytes(1, byteorder='big')

    
    request = address+b'\x08\x01'
    lo, hi  = crc16(request)
    request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')

    request += access_request(address)
    responce = await queue_tx_put(request+EOF, False)
        #check responce
    if type(responce) == str:
        text = "Значение внутренней температуры счетчика:\n\n" + responce
    else:
        if len(responce) != 5:
            err_num = responce[1:2]
            if err_num in set4tm_errors: text += set4tm_errors[err_num]
            else: text = "Значение внутренней температуры счетчика:\n\n" + f'unknown error code: {hex(int.from_bytes(err_num, "big"))}'
        else:
            t = int.from_bytes(responce[2:3], "big")
            if t > 127: t -= 256
            si = " °C"
            text += "🌡: "+str(t)+si+"\n"
            globals()["last_time_responce"] = str(round(time.time()-start_time, 2)) +" c"
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass

    REQUESTS.pop(update.callback_query.from_user.id, 1)

    return MAIN

def access_request(address :bytes):
    energy_password = CONFIG["DEVICE_PASSWORD"]
    energy_password = energy_password.encode()
    request = address+b'\x01'+energy_password
    lo, hi  = crc16(request)
    request += lo.to_bytes(1, byteorder='big') + hi.to_bytes(1, byteorder='big')
    return request

async def view_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["user"].load_from_db()
    if context.user_data["user"].notify == 0: notify = "отключены"
    if context.user_data["user"].notify == 1: notify = "включены"
    if context.user_data["user"].notify == 2: notify = "без звука"
    text = "Настройки:\n\n"+f"🔔 Уведомления: {notify}"
    keyboard = [
                [InlineKeyboardButton("🔔 Уведомления", callback_data="notify")],
                [InlineKeyboardButton("🏠", callback_data="home")],
                ]
    if update.message:
        context.chat_data["last_message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.answer()
        try:
            context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
        except BadRequest: pass
    return SETTINGS

async def stat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    text = "Cтатистика:\n\nВыберите период для показа статистики"
    keyboard = [
                [InlineKeyboardButton("Год", callback_data="year"),
                InlineKeyboardButton("Месяц", callback_data="month"),
                InlineKeyboardButton("День", callback_data="day"),],
                [InlineKeyboardButton("🏠", callback_data="home"),],
                ]

    await update.callback_query.answer()
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    return STAT
async def year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    text = "Cтатистика за последние 12 месяцев:\n\n"
    keyboard = [
                [InlineKeyboardButton("Обновить", callback_data="year"),
                InlineKeyboardButton("Месяц", callback_data="month"),
                InlineKeyboardButton("День", callback_data="day"),],
                [InlineKeyboardButton("🏠", callback_data="home"),],
                ]

    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    # try:
    now = datetime.datetime.now()
    data = {}
    for i in range(12):
        if i == 0:
            d1 = decrease_months(now, i).strftime('%Y-%m')
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

            d2 = now.strftime('%Y-%m-%d %H:%M:%S')
            d_dt2 = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S')

            cursor.execute('SELECT * FROM active_energy WHERE date > DATE("'+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+'") LIMIT 1')
            energy1 = cursor.fetchone()
            cursor.execute('SELECT * FROM active_energy ORDER BY date DESC LIMIT 1')
            energy2 = cursor.fetchone()
        else:
            d1 = decrease_months(now, i).strftime('%Y-%m')
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

            d2 = decrease_months(now, i-1).strftime('%Y-%m')
            d_dt2 = datetime.datetime.strptime(d2, '%Y-%m')

            cursor.execute('SELECT * FROM active_energy WHERE date > DATE("'+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+'") LIMIT 1')
            energy1 = cursor.fetchone()
            cursor.execute('SELECT * FROM active_energy WHERE date > DATE("'+d_dt2.strftime('%Y-%m-%d %H:%M:%S')+'") LIMIT 1')
            energy2 = cursor.fetchone()

        if energy1 and energy2:
            diff_energy = round((energy2[1] - energy1[1]), 3)
            data.update({d_dt1.strftime('%m'):diff_energy})
        else: 
            data.update({d_dt1.strftime('%m'):0})
    # except Exception as e:
    #     logger.error("Exception: "+str(e)+" in load from DB active_energy")
    # finally:
    sqlite_connection.close()

    max_value = data[max(data, key=data.get)]
    for key, value in data.items():
        text += num_to_scale(percent_value=(value/max_value)*100, numsimb=16, add_percent=False, prefix=key+": ", value=value, si="кВт*ч") +"\n"

    await update.callback_query.answer()
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass

    return STAT
def decrease_months(sourcedate, months):
    month = sourcedate.month - 1 - months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year,month)[1])
    return datetime.date(year, month, day)
async def month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    cb = update.callback_query.data
    if "0%" in cb:
        #TODO get from bd
        mounth = re.findall(r'0%(.+)1%', cb)[0]
        d1 = re.findall(r'1%(.+)2%', cb)[0]
        d2 = re.findall(r'2%(.+)', cb)[0]
        end = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S')


        text = "Cтатистика за "+str(mounth)+" месяц:\n\n"

        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()

        # get data every day
        data={}
        for i in range(31):
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(days=i)
            d_dt2 = datetime.datetime.strptime(d1, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(days=i+1)
            if d_dt1 >= end: break
            cursor.execute('SELECT * FROM active_energy WHERE date > DATE("'+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+'") LIMIT 1')
            energy1 = cursor.fetchone()
            if d_dt2 >= datetime.datetime.now():
                cursor.execute('SELECT * FROM active_energy ORDER BY date DESC LIMIT 1')
                energy2 = cursor.fetchone()
            else:
                cursor.execute('SELECT * FROM active_energy WHERE date > DATE("'+d_dt2.strftime('%Y-%m-%d %H:%M:%S')+'") LIMIT 1')
                energy2 = cursor.fetchone()

            if energy1 and energy2:
                diff_energy = round((energy2[1] - energy1[1]), 3)
                data.update({d_dt1.strftime('%d'):diff_energy})
            else: 
                data.update({d_dt1.strftime('%d'):0})
        sqlite_connection.close()
        max_value = data[max(data, key=data.get)]
        for key, value in data.items():
            if max_value: percent = value/max_value
            else: percent = 0
            text += num_to_scale(percent_value=(percent)*100, numsimb=16, add_percent=False, prefix=key+": ", value=value, si="кВт*ч") +"\n"

    else:
        text = "Cтатистика:\n\nВыберите месяц для показа статистики"
    keyboard = [[]]
    for i in range(12):
        now = datetime.datetime.now()
        if i == 0:
            d1 = decrease_months(now, i).strftime('%Y-%m')
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

            d2 = now.strftime('%Y-%m-%d %H:%M:%S')
            d_dt2 = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S')
        else:
            d1 = decrease_months(now, i).strftime('%Y-%m')
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

            d2 = decrease_months(now, i-1).strftime('%Y-%m')
            d_dt2 = datetime.datetime.strptime(d2, '%Y-%m')

        if len(keyboard) <= ((i) // 4):
            keyboard.append([])
        keyboard[(i) // 4].append(InlineKeyboardButton(d_dt1.strftime('%m'), callback_data="month0%"+d_dt1.strftime('%m')+"1%"+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+"2%"+d_dt2.strftime('%Y-%m-%d %H:%M:%S')))

    keyboard.append([InlineKeyboardButton("⬅", callback_data="stat"), 
                    InlineKeyboardButton("🏠", callback_data="home")])

    await update.callback_query.answer()
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    return STAT
async def day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cb = update.callback_query.data
    #get day stat
    data={}
    if "0%d" in cb:
        day = re.findall(r'0%d(.+)1%', cb)[0]
        d1 = re.findall(r'1%(.+)2%', cb)[0]
        d_dt1 = datetime.datetime.strptime(d1, '%Y-%m-%d %H:%M:%S')
        month = d_dt1.strftime('%m')

        d2 = re.findall(r'2%(.+)', cb)[0]
        d_dt2 = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=1)
        
        text = "Cтатистика за "+day+" день "+month+" месяц:\n\n"

        sqlite_connection = sqlite3.connect(DB_PATCH)
        cursor = sqlite_connection.cursor()
        cursor.execute('SELECT * FROM active_energy WHERE date > "'+d1+'" AND date < "'+d_dt2.strftime('%Y-%m-%d %H:%M:%S')+'"')
        energy = cursor.fetchall()
        for i, res in enumerate(energy):
            if i+1 >= len(energy): break
            key_dt = datetime.datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            key_st = key_dt.strftime('%H:%M')
            value = round(energy[i+1][1] - res[1], 3)
            data.update({key_st:value})
        if data:
            max_value = data[max(data, key=data.get)]
        else: max_value = 0

        for key, value in data.items():
            if max_value: percent = value/max_value
            else: percent = 0
            text += num_to_scale(percent_value=(percent)*100, numsimb=16, add_percent=False, prefix=key+": ", value=value, si="кВт*ч") +"\n"

    #get month
    elif "0%m" in cb:
        keyboard = [[]]
        month = re.findall(r'0%m(.+)1%', cb)[0]
        d1 = re.findall(r'1%(.+)2%', cb)[0]
        d2 = re.findall(r'2%(.+)', cb)[0]
        end = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S')
        text = "Cтатистика:\n\nВыберите день для показа статистики"

        for i in range(31):
            d_dt1 = datetime.datetime.strptime(d1, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(days=i)
            d_dt2 = datetime.datetime.strptime(d1, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(days=i+1)
            if d_dt1 >= end: break
            #create keyboard
            if len(keyboard) <= ((i) // 8):
                keyboard.append([])
            keyboard[(i) // 8].append(InlineKeyboardButton(d_dt1.strftime('%d'), callback_data="day0%d"+d_dt1.strftime('%d')+"1%"+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+"2%"+d_dt2.strftime('%Y-%m-%d %H:%M:%S')))

        keyboard.append([InlineKeyboardButton("⬅", callback_data="day"), 
                        InlineKeyboardButton("🏠", callback_data="home")])

    else:
        text = "Cтатистика:\n\nВыберите месяц для показа статистики"
        keyboard = [[]]
        for i in range(12):
            now = datetime.datetime.now()
            if i == 0:
                d1 = decrease_months(now, i).strftime('%Y-%m')
                d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

                d2 = now.strftime('%Y-%m-%d %H:%M:%S')
                d_dt2 = datetime.datetime.strptime(d2, '%Y-%m-%d %H:%M:%S')
            else:
                d1 = decrease_months(now, i).strftime('%Y-%m')
                d_dt1 = datetime.datetime.strptime(d1, '%Y-%m')

                d2 = decrease_months(now, i-1).strftime('%Y-%m')
                d_dt2 = datetime.datetime.strptime(d2, '%Y-%m')

            if len(keyboard) <= ((i) // 4):
                keyboard.append([])
            keyboard[(i) // 4].append(InlineKeyboardButton(d_dt1.strftime('%m'), callback_data="day0%m"+d_dt1.strftime('%m')+"1%"+d_dt1.strftime('%Y-%m-%d %H:%M:%S')+"2%"+d_dt2.strftime('%Y-%m-%d %H:%M:%S')))

        keyboard.append([InlineKeyboardButton("⬅", callback_data="stat"), 
                        InlineKeyboardButton("🏠", callback_data="home")])


    if "keyboard" in locals():
        reply_markup = InlineKeyboardMarkup(keyboard)
    else: reply_markup = update.callback_query.message.reply_markup

    await update.callback_query.answer()
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except BadRequest: pass
        
    return STAT


async def dop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    text = "Дополнительные запросы:\n\n"
    keyboard = [
                [InlineKeyboardButton("Мощность", callback_data="power"),
                InlineKeyboardButton("Напряжение", callback_data="voltage"),
                InlineKeyboardButton("Ток", callback_data="current"),],
                [InlineKeyboardButton("🏠", callback_data="home"),
                InlineKeyboardButton("Частота", callback_data="freq"),
                InlineKeyboardButton("Температура", callback_data="temperature")],
                ]

    await update.callback_query.answer()
    try:
        context.chat_data["last_message"] = await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    except BadRequest: pass
    return MAIN

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    #notification
    if update.callback_query.data == "notify":
        context.user_data["user"].notify += 1
        if context.user_data["user"].notify == 3: context.user_data["user"].notify = 0
        context.user_data["user"].save_to_db(["notify"])
    await view_settings(update, context)
    return SETTINGS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, end_point=False) -> int:
    """Cancels and ends the conversation."""
    if update.message: u = update.message.from_user
    else: u = update.callback_query.from_user

    logger.info("User canceled the conversation." +str(u.first_name))

    text = "🏁 Диалог окончен"
    keyboard = [[InlineKeyboardButton("🏳 Начать", callback_data="main")]]
    if end_point and context.chat_data["last_message"] and context.chat_data["last_message"].text != text:
        await context.chat_data["last_message"].edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        if update.message:
            await update.message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
            )
        else:
            if update.callback_query.message.text != text or update.callback_query.message.reply_markup != InlineKeyboardMarkup(keyboard):
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
                )
            else: 
                await update.callback_query.answer()

    context.chat_data.clear
    context.user_data.clear
    return ConversationHandler.END

async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await cancel(update, context, end_point=True)

async def logout_bt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    u = update.callback_query.from_user
    if "user" in context.user_data:
        context.user_data["user"].auth = "GUEST"
        context.user_data["user"].save_to_db(params="auth")
        context.user_data.clear
    else:
        user = User(id=u.id)
        user.save_to_db(params="auth")
    await start(update, context)
    return AUTH

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message: return ConversationHandler.END
    u = update.message.from_user
    if "user" in context.user_data:
        context.user_data["user"].auth = "GUEST"
        context.user_data["user"].save_to_db(params="auth")
        context.user_data.clear
    else:
        user = User(id=u.id)
        user.save_to_db(params="auth")
    context.chat_data["last_message"] = await update.message.reply_text(
        "🏁 Вы вышли", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏳 Начать", callback_data="main")]])
    )
    return ConversationHandler.END

async def black_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ip = update.callback_query.data[len("black_ip"):]
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        cursor.execute('''SELECT ip FROM BlackIPs WHERE ip = ?''', (ip,))
        if not cursor.fetchall(): 
            cursor.execute('''INSERT INTO BlackIPs VALUES(?,?)''', (ip, datetime.datetime.now()))
            sqlite_connection.commit()
            BLACK_IPS.add(ip)
        await send_simple_message(ip+" in Black list", True)
        return True
    except Exception as e:
        logger.error("Exception: "+str(e)+" in save to DB black ip")
        return False
    finally:
        sqlite_connection.close()
        return MAIN
    

async def send_simple_message(text, admin=False, add_button=None):
    if type(text) == bytes: text = text.decode()
    st = text.find('Software')
    if st != -1:
        globals()["start_time"] = datetime.datetime.now()
        new_device_addr = re.findall(pattern=r'Device address: (\d+)', string=text)
        if new_device_addr and new_device_addr[0] != CONFIG["DEVICE_ADDRESS"]:
            globals()["CONFIG"]["DEVICE_ADDRESS"] = int(new_device_addr[0])
            with open(CONFIG_PATCH, "w") as f:
                f.write(yaml.dump(CONFIG, sort_keys=False))
        rssi_start = re.search(pattern=r'RSSI:(\d+)', string=text)
        if rssi_start.start():
            rssi = re.findall(pattern=r'RSSI:(\d+)', string=text)[0]
            text = re.sub(pattern=r'RSSI:(\d+)', repl=signal_to_scale(rssi), string=text)
            text = re.sub(pattern=r'GSM Operator', repl='GSM оператор', string=text)
            text = re.sub(pattern=r'Software version', repl='Версия ПО', string=text)
            text = re.sub(pattern=r'Modem was started', repl='Модем успешно запущен', string=text)
            text = re.sub(pattern=r'Device online', repl='Устройство онлайн', string=text)
            text = re.sub(pattern=r'Device address', repl='Адрес устройства', string=text) 
        globals()["device_status"] = re.sub(pattern=r'Модем успешно запущен', repl='', string=text)

    logger.info(f'message: {text}')

    keyboard = [[]]
    keyboard[0].extend(
        [
            InlineKeyboardButton("🏠", callback_data="home"),],
    )
    if add_button:
        keyboard[0].append(InlineKeyboardButton(add_button[0], callback_data=add_button[1]))
    if not admin: 
        users = load_all_users(['notify', 1])
        for user in users:
            await application.bot.send_message(user.id, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_notification=False)
        users = load_all_users(['notify', 2])
        for user in users:
            await application.bot.send_message(user.id, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_notification=True)
    else: 

        users = load_all_users(['auth', "'ADMIN'"])
        for user in users:
            if user.notify == 1:
                await application.bot.send_message(user.id, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_notification=False)
            elif user.notify ==2:
                await application.bot.send_message(user.id, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_notification=True)
            else: continue


async def socket_server(context: CallbackContext):
    server = await asyncio.start_server(
        new_connection, host=CONFIG["SOCKET_IP"], port=CONFIG["SOCKET_PORT"], backlog=1)
    addr = server.sockets[0].getsockname()
    logger.info(f'Serving on {addr}')

    async with server:
        await server.serve_forever()

async def new_connection(reader, writer):
    addr = writer.get_extra_info('peername')
    if addr and str(addr[0]) in BLACK_IPS:
        writer.close()
        return
    #Check password
    s_pass = await reader.read(len(CONFIG["SOCKET_PASS"].encode()))
    s_pass = s_pass.decode()
    if s_pass != CONFIG["SOCKET_PASS"]:
        text = f"Попытка авторизации адресом {addr!r}. Введен пароль {s_pass!r}. Соединение с адресом разорвано"
        logger.warning(text)
        if addr and transmitters.qsize() == 0:
            ip = addr[0]
            await send_simple_message(text, True, add_button=["BLACK LIST", "black_ip"+str(ip)])
        writer.close()
        return
    logger.info("New connection from "+str(addr))
    task = asyncio.create_task(transmiter(writer))
    if transmitters.qsize() == 1:
        old_task = transmitters.get_nowait()
        old_task.cancel()
    transmitters.put_nowait(task)
    if addr:
        text = f"Успешная авторизация с адреса {addr!r}"
        await send_simple_message(text, True, add_button=["BLACK LIST", "black_ip"+str(addr[0])])

    timeout_EOF = 0
    while True:
        try:
            if not ("bdata" in locals() and EOF in bdata):
                read = await reader.read(100)
                if len(read) == len(b'+++') and read == b'+++':
                    continue
                if "bdata" in locals(): bdata +=read
                else: bdata = read
                logger.info('Get bytes: ' +(str(bdata)))
                if timeout_EOF == 0:
                    timeout_EOF = time.time() + 10
        except ConnectionResetError:
            logger.error("RX, ConnectionResetError")
            if transmitters.qsize() == 1: transmitters.get_nowait()
            writer.close()
            task.cancel()
            await asyncio.sleep(1)
            await queue_rx.put("RX, ConnectionResetError")
            return
        
        if EOF in bdata:
            timeout_EOF = 0
            delimeter_position = bdata.find(EOF)
            data_recieved = bdata[:delimeter_position]
            bdata = bdata[delimeter_position+len(EOF):]

            logger.info("Received: " +str(data_recieved)+ f" from {addr!r}")

            if RESPONCE in data_recieved:
                data_recieved = data_recieved[len(RESPONCE):]
                try:
                    await asyncio.wait_for(queue_rx.put(data_recieved), 1)
                except asyncio.TimeoutError:
                    await queue_rx.get()
                    await queue_rx.put(data_recieved)
                    logger.error("queue_rx was full for data recieved")
            elif MESSAGE in data_recieved:
                data_recieved = data_recieved[len(MESSAGE):]
                await send_simple_message(data_recieved)
            else:
                await send_simple_message(data_recieved, True)
                
        if not read or (timeout_EOF != 0 and time.time() > timeout_EOF):
            logger.error("Empty read or timeout getting data")
            if transmitters.qsize() == 1: transmitters.get_nowait()
            writer.close()
            task.cancel()
            return

async def transmiter(writer):
    while True:
        for_send = await queue_tx.get()
        writer.write(for_send)
        try:
            await writer.drain()
        except ConnectionResetError:
            logger.warning(f"TX, ConnectionResetError")
            await asyncio.sleep(1)
            try: queue_rx.put_nowait("TX, ConnectionResetError")
            except asyncio.QueueFull: logger.error("queue_rx is full for TX, ConnectionResetError")
            finally: queue_tx.task_done()
            return

async def queue_tx_put(request, wait=False):
    try:
        await asyncio.wait_for(queue_tx.join(), 30)
    except asyncio.TimeoutError:
        text = "Слишком много запрососов от пользователей, попробуйте повторить позднее"
        return text
    await queue_tx.put(request)
    #clear old responce if it was
    try:
        text = await asyncio.wait_for(queue_rx.get(), 0.5)
        logger.warning(f"Geted old responce!!!")
        await send_simple_message("Geted old responce", True)
    except asyncio.TimeoutError:
        pass
    #get new responce
    try:
        text = await asyncio.wait_for(queue_rx.get(), 40)
    except asyncio.TimeoutError:
        text = "No responce, timeout error"
    finally:
        #clear queue_tx
        try: queue_tx.get_nowait()
        except asyncio.QueueEmpty: pass
        queue_tx.task_done()
    return text

def check_config(config):
    if not "SIM_PHONE" in config:
        config["SIM_PHONE"] = "unknown"
    if not "DEVICE_A" in config:
        config["DEVICE_A"] = 1250
    if not "DEVICE_Kc" in config:
        config["DEVICE_Kc"] = 1
    if not "DEVICE_Ktt" in config:
        config["DEVICE_Ktt"] = '1/1'
    if not "DEVICE_Ktn" in config:
        config["DEVICE_Ktn"] = '1/1'
    if not "DEVICE_PASSWORD" in config: 
        config["DEVICE_PASSWORD"] = '000000'
    if not "DEVICE_ADDRESS" in config:
        config["DEVICE_ADDRESS"] = 46
    if not "SOCKET_IP" in config:
        config["SOCKET_IP"] = '0.0.0.0'
    if not "SOCKET_PORT" in config:
        config["SOCKET_PORT"] = 3000
    if not "TOKEN" in config:
        logger.error("There is no TOKEN in config.yaml")
        exit()
    if not "PASSWORD" in config:
        logger.error("There is no PASSWORD in config.yaml")
        exit()
    if not "SOCKET_PASS" in config:
        logger.error("There is no SOCKET_PASS in config.yaml")
        exit()
    return config



if __name__ == '__main__':
    SLASH = check_system()
    dir = get_script_dir()
    CONFIG_PATCH = dir+SLASH+"config.yaml"
    if not os.path.exists(CONFIG_PATCH):
        print("config.yaml file not exist")
        time.sleep(2)
        exit()
    else:
        with open(CONFIG_PATCH, encoding='utf-8') as f:
            CONFIG = yaml.load(f.read(), Loader=yaml.FullLoader)
    CONFIG = check_config(CONFIG)
    # Enable logging
    level = logging.INFO
    if "LOG_LEVEL" in CONFIG:
        if CONFIG["LOG_LEVEL"] == "INFO": pass
        if CONFIG["LOG_LEVEL"] == "ERROR": level=logging.ERROR
        if CONFIG["LOG_LEVEL"] == "WARNING" or CONFIG["LOG_LEVEL"] == "WARN": level=logging.ERROR
        if CONFIG["LOG_LEVEL"] == "NOTSET": level=logging.NOTSET
    logging.basicConfig(
        datefmt='%H:%M:%S',
        format="%(asctime)s   %(funcName)s(%(lineno)d) - %(levelname)s - %(message)s", 
        level=level
    )
    logger = logging.getLogger(__name__)

    #DB CONNECT
    DB_PATCH = dir+SLASH+'users.db'
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    BLACK_IPS = set()
    try:
        cursor.execute("""CREATE TABLE if not exists users
                        (id integer NOT NULL UNIQUE, name text, surname text, auth text, tryn integer, notify integer)
                    """)
        sqlite_connection.commit()
        cursor.execute("""CREATE TABLE if not exists BlackIPs
                        (ip text NOT NULL UNIQUE, time text)
                    """)
        sqlite_connection.commit()
        cursor.execute("""CREATE TABLE if not exists active_energy
                        (date timestamp NOT NULL UNIQUE, value REAL)
                    """)
        sqlite_connection.commit()

    #load black_list
        request = '''SELECT * FROM BlackIPs'''
        cursor.execute(request)
        ips = cursor.fetchall()
        if ips:
            for ip in ips:
                BLACK_IPS.add(ip[0])

    except Exception as e:
        logger.error("Exception: %s at DB connect.", e)
    sqlite_connection.close()

    #create queues for requests
    queue_rx = asyncio.Queue(1)
    queue_tx = asyncio.Queue(1)
    transmitters = asyncio.Queue(1) #only one transmitter can work
    #create flag request
    REQUESTS = {}
    #Constant end of message
    EOF = b'%end%'
    MESSAGE = b'message'
    RESPONCE = b'responce'
    RESTART = b'restart'
    FOTA = b'fota_update'
    APPLY = b'apply'
    TRIPLE = b'triple'

    #Globals vars
    device_status = ''
    last_time_responce = 'unknown'
    start_time = datetime.datetime.now()
    
    #save energy at the start every hour
    scheduler = apscheduler.schedulers.asyncio.AsyncIOScheduler()
    start_date = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H")
    scheduler.add_job(save_energy_to_db, 'interval', hours=1, start_date=datetime.datetime.strptime(start_date, "%Y-%m-%d %H"))
    scheduler.add_job(delete_energy_from_db, 'interval', days=2, start_date=datetime.datetime.strptime(start_date, "%Y-%m-%d %H"))
    scheduler.start()

    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(CONFIG["TOKEN"]).concurrent_updates(10).build()
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),
                        CommandHandler("logout", logout),
                        CallbackQueryHandler(black_ip, pattern='^black_ip'),
                        CallbackQueryHandler(start, pattern='^')],
        states={
            AUTH: [CommandHandler("start", start),
                    CommandHandler("stop", cancel),
                    CommandHandler("cancel", cancel),
                    MessageHandler(filters.TEXT, auth),
                    CallbackQueryHandler(black_ip, pattern='^black_ip')],
            MAIN: [CommandHandler("start", start),
                    CommandHandler("stop", cancel),
                    CommandHandler("cancel", cancel),
                    CommandHandler("logout", logout),
                    CommandHandler("fota", fota_start),
                    CommandHandler("reboot", restart),
                    CallbackQueryHandler(energy, pattern='^energy'),
                    CallbackQueryHandler(main_menu, pattern='^home'),
                    CallbackQueryHandler(logout_bt, pattern='^logout'),
                    CallbackQueryHandler(dop, pattern='^dop'),
                    CallbackQueryHandler(view_settings, pattern='^settings'),
                    CallbackQueryHandler(power, pattern='^power'),
                    CallbackQueryHandler(voltage, pattern='^voltage'),
                    CallbackQueryHandler(current, pattern='^current'),
                    CallbackQueryHandler(freq, pattern='^freq'),
                    CallbackQueryHandler(temperature, pattern='^temperature'),
                    CallbackQueryHandler(black_ip, pattern='^black_ip'),
                    CallbackQueryHandler(stat, pattern='^stat')],
            FOTA: [CommandHandler("stop", cancel),
                    CommandHandler("cancel", cancel),
                    CommandHandler("fota", fota_start),
                    CommandHandler("reboot", restart),
                    CallbackQueryHandler(main_menu, pattern='^home'),
                    MessageHandler(filters.Document.ALL, fota_send_file),
                    CallbackQueryHandler(black_ip, pattern='^black_ip')],
            SETTINGS: [CommandHandler("stop", cancel),
                        CommandHandler("cancel", cancel),
                        CommandHandler("logout", logout),
                        CommandHandler("fota", fota_start),
                        CommandHandler("reboot", restart),
                        CallbackQueryHandler(main_menu, pattern='^home'),
                        CallbackQueryHandler(settings, pattern='^notify$'),
                        CallbackQueryHandler(black_ip, pattern='^black_ip')],
            STAT: [CommandHandler("start", start),
                        CommandHandler("stop", cancel),
                        CommandHandler("cancel", cancel),
                        CommandHandler("logout", logout),
                        CommandHandler("fota", fota_start),
                        CommandHandler("reboot", restart),
                        CallbackQueryHandler(main_menu, pattern='^home'),
                        CallbackQueryHandler(stat, pattern='^stat'),
                        CallbackQueryHandler(day, pattern='^day'),
                        CallbackQueryHandler(year, pattern='^year'),
                        CallbackQueryHandler(month, pattern='^month'),],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, timeout),
                                            CallbackQueryHandler(timeout, pattern='^'),],
        },
        conversation_timeout = 300,
        fallbacks=[CommandHandler("cancel", cancel)],
    )


    application.add_handler(conv_handler)
    jobs = application.job_queue
    jobs.run_once(callback=socket_server, when=2)  
    application.run_polling(connect_timeout=10, pool_timeout=10, read_timeout=5, write_timeout=5)
    
