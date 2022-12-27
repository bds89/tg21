import MOD
import MDM
import SER
from crc16 import check_crc16, NO_CARRIER, crc16
from sms import smsinit, sms_handler
from init import init

OPERATORS = ["beeline", "megafon", "tele2", "mts"]
OP_SYMBOLS = {"beeline":"BbEeEeLlIiNnEeRrUuSs", "megafon":"MmEeGgAaFfOoNnRrUuSs", "tele2":"TtEeLlEe2RrUuSs", "mts":"MmTtSRrUuSs"}
AP = {
    "beeline": "internet.beeline.ru",
    "megafon": "internet",
    "tele2": "internet.tele2.ru",
    "mts": "internet.mts.ru"
}
USER = {
    "beeline": "beeline",
    "megafon": "",
    "tele2": "",
    "mts": "mts"
}
PASSWORD = {
    "beeline": "beeline",
    "megafon": "",
    "tele2": "",
    "mts": "mts"
}

TIMEOUT_AT = 10
TIMEOUT_NET = 15
TIMEOUT_485 = 5
SPEED485 = ('9600', '8O1') #str, tuple
PKTSIZE = '1200' #bytes
S_NO_DATA_TIMEOUT = '65535' #seconds, str
S_CON_TIMEOUT = '300' #1/10 seconds, str
S_PORT = '3000' #strы
S_IP = '192.168.1.1' #str
S_PASS = '1111' #str
PERIODIC_RECONNECT = 43200 #seconds, int
SMS_CHECK = 300 #seconds, int
DEVICE_ADDRESS = 46 #int, < 255 (one byte)
DEVICE_PASSWORD = '000000' #str, 6 chars
DEVICE_A = 1250 #int, device energy constant
VERSION = '1.19' #str

def cmdAT(cmd, result, time_out, recursive_n = 0):
    if recursive_n > 2: MOD.sleep(30)
    MDM.send(cmd, 0)
    timeout = MOD.secCounter() + time_out
    res = MDM.receive(TIMEOUT_AT)
    while (res.find(result) == -1 and MOD.secCounter() < timeout):
        res = res + MDM.receive(TIMEOUT_AT)
    if (res.find(result) == -1):
        if cmd == '+++':
            if cmdAT('AT\r', 'OK', 1) == 1:
                return 1
            else: cmdAT('+++', 'OK', time_out+1, recursive_n+1)
        return 0
    else: return 1



def enable_script(filename):
    cmdAT('+++', 'OK', 2)
    if (cmdAT('AT#ESCRIPT="'+filename+'"\r', 'OK', 2) == 1):
        return 1
    else:
        return 0

def write_file(new_file, file_code):
    cmdAT('+++', 'OK', 2)
    if file_code == 1:
        file_name = "sms.pyo"
    elif file_code == 2:
        file_name = "crc16.pyo"
    else:
        MDM.send('AT#ESCRIPT?\r', 0)
        timeout = MOD.secCounter() + 5
        ok = MDM.receive(TIMEOUT_AT)
        while (((ok.find("bot.pyo") == -1) and (ok.find("bot2.pyo") == -1)) and MOD.secCounter() < timeout):
            ok = ok + MDM.receive(TIMEOUT_AT)
        if ((ok.find("bot.pyo") == -1) and (ok.find("bot2.pyo") == -1)):
            return 0
        if (ok.find("bot.pyo") == -1): file_name = "bot.pyo"
        else: file_name = "bot2.pyo"
    try:
        f = open(file_name, "wb")
        try:
            f.write(new_file)
            f.flush()
            f.close()
            if file_code != 0: return 1
            if (enable_script(file_name) == 1): 
                return 1
            else: return 0
        finally:
            if (cmdAT('AT#SO=1\r', 'CONNECT', 2) == 0):
                cmdAT('AT#REBOOT\r', 'OK', 2)
    except IOError:
        return 0

def socket_recieve(withsms):
    data_recieved = ""
    period_reconnect = MOD.secCounter() + PERIODIC_RECONNECT
    sms_check = MOD.secCounter() + SMS_CHECK
    while(1==1):
        MOD.watchdogReset()
        data_recieved = data_recieved + MDM.receive(TIMEOUT_AT*2)
        if len(data_recieved) == 0:
            if MOD.secCounter() > sms_check:
                if withsms == 1:
                    sms_handler(DEVICE_ADDRESS, DEVICE_PASSWORD, DEVICE_A)
                    if cmdAT('AT#SO=1\r', 'CONNECT', 2) == 0:
                        return ""
                sms_check = MOD.secCounter() + SMS_CHECK
            if MOD.secCounter() > period_reconnect:
                cmdAT('+++', 'OK', 2)
                cmdAT('AT#SH=1\r', 'OK', 10)
                return ""
            continue
        else:
            if data_recieved.find(EOF) != -1:
                delimeter_position = data_recieved.find(EOF)
                request = data_recieved[:delimeter_position]
                return request
            if (data_recieved.find(NO_CARRIER) != -1):
                return ""
            else: continue

def socket485(request, triple=0):
    SER.read() #clear buffer
    energy_address = request[:1]
    access_request = request[-10:]

    request = request[:-10]

    #get access
    SER.send(access_request)
    res = ""
    timeout = MOD.secCounter() + TIMEOUT_485
    res = SER.read()
    while((check_crc16(res) == 0) and (MOD.secCounter() < timeout)):
        MOD.sleep(5)
        res = res + SER.read()
    if check_crc16(res) == 0:
        return(energy_address+chr(0x0B)+chr(0x00)+chr(0x00))  #no responce from device

    if res[:2] != (energy_address+chr(0x00)):
        return res
    #make main request
    if triple == 1:
        request_list = [request[0:6], request[6:12], request[12:18]]
    else:
        request_list = [request]
    answer = ""
    for request in request_list:
        SER.send(request)
        res = ""
        timeout = MOD.secCounter() + TIMEOUT_485
        res = SER.read()
        while((check_crc16(res) == 0) and (MOD.secCounter() < timeout)):
            MOD.sleep(5)
            res = res + SER.read()
        if (check_crc16(res) == 0):
            return(energy_address+chr(0x0B)+chr(0x00)+chr(0x00))  #no responce from device
        answer = answer + res
    return answer

def check_device_addr485():
    SER.read() #clear buffer
    request = chr(DEVICE_ADDRESS)+chr(0x00)
    request_crc = crc16(request)
    SER.send(request_crc)
    res = ""
    timeout = MOD.secCounter() + 5
    res = SER.read()
    while((request_crc != res) and (MOD.secCounter() < timeout)):
        MOD.sleep(10)
        res = res + SER.read()
    if (request_crc != res): return 0
    else: return 1

def internet_off():
    f_name = "internet.txt"
    try:
        f = open(f_name, "a")
        f.close()

        f = open(f_name, "r")
        internet = f.read()
        f.close()
        if internet != "off": return 0
        else: return 1
    except IOError:
        return 0

def main():
    operator, signal_str = init(
    SPEED485, 
    OPERATORS,
    OP_SYMBOLS,
    AP,
    USER,
    PASSWORD,
    )
    device_online = 0
    if check_device_addr485() == 0:
        request = chr(0x00)+chr(0x08)+chr(0x05)
        request_crc = crc16(request)
        SER.send(request_crc)
        res = ""
        timeout = MOD.secCounter() + 5
        res = SER.read()
        while((check_crc16(res) == 0) and (MOD.secCounter() < timeout)):
            MOD.sleep(10)
            res = res + SER.read()
        if (check_crc16(res) == 0):
            device_online = 0
        else:
            globals()["DEVICE_ADDRESS"] = ord(res[2:3])
            device_online = check_device_addr485()
    else: device_online = 1

    withsms = smsinit()
    #Only sms loop
    if internet_off() == 1 and withsms == 1:
        #will reboot every 2 days
        MOD.watchdogDisable()
        MOD.watchdogEnable(172800)
        while(1==1):
            sms_handler(DEVICE_ADDRESS, DEVICE_PASSWORD, DEVICE_A)
            MOD.sleep(100)
    #socket config
    if (cmdAT('AT#SCFG=1,1,'+PKTSIZE+','+S_NO_DATA_TIMEOUT+','+S_CON_TIMEOUT+',50\r', 'OK', 2) == 0):
        cmdAT('AT#REBOOT\r', 'OK', 2)
    #main loop
    try_connect = 0
    fota_process = 0
    while(try_connect < 720):
        #socket connect
        if (cmdAT('AT#SD=1,0,'+S_PORT+','+S_IP+'\r', 'CONNECT', 120) == 0):
            try_connect = try_connect + 1
            sms_handler(DEVICE_ADDRESS, DEVICE_PASSWORD, DEVICE_A)
            continue
        #send message about start modem
        MDM.send(S_PASS, 0)
        if try_connect == 0:
            MOD.sleep(10)
            MDM.send((MESSAGE+'Modem was started\nSoftware version: '+VERSION\
            +'\nGSM Operator: '+operator+'\nRSSI:'+signal_str+"\nDevice online: "+str(device_online)\
                +"\nDevice address: "+str(DEVICE_ADDRESS)+EOF), 0)
        try_connect = 0
        
        connection = 1
        while(connection==1):
            request = socket_recieve(withsms)
            if not request:
                try_connect = try_connect + 1
                break
            #if command in request
            if request.find(RESTART) != -1:
                MDM.send((RESPONCE+'Manual restart initialized'+EOF), 0)
                MOD.sleep(10)
                cmdAT('+++', 'OK', 2)
                cmdAT('AT#REBOOT\r', 'OK', 5)

            if request.find(FOTA) != -1:
                fota_process = 1
                MDM.send((RESPONCE+FOTA+str(int(PKTSIZE)-1)+EOF), 0)
                file_code = int(request[len(FOTA):len(FOTA)+1])
                file_lenght = int(request[len(FOTA)+1:])
                data_recieved = ""
                pkt_recieved = ""
                RESPONCE_TO = (int(PKTSIZE)/10)+10
                timeout = MOD.secCounter() + RESPONCE_TO
                while(MOD.secCounter() < timeout):
                    pkt = MDM.receive(TIMEOUT_485)
                    data_recieved = data_recieved + pkt
                    pkt_recieved = pkt_recieved + pkt
                    if (data_recieved.find(NO_CARRIER) != -1):
                        connection = 0
                        break
                    if len(data_recieved) != file_lenght:
                        if (len(pkt_recieved) < int(PKTSIZE)-1): continue
                        else:
                            MDM.send((RESPONCE+FOTA+str(len(data_recieved))+EOF), 0)
                            timeout = MOD.secCounter() + RESPONCE_TO
                            pkt_recieved = ""
                        continue
                    else:
                        MDM.send((RESPONCE+FOTA+str(len(data_recieved))+EOF), 0)
                        #recieve apply message
                        timeout = MOD.secCounter() + 30
                        apply = ""
                        while(apply.find(APPLY) == -1 and MOD.secCounter() < timeout):
                            apply = apply + MDM.receive(TIMEOUT_485)
                        break

                #write data to file
                if len(data_recieved) == file_lenght:
                    w = write_file(data_recieved, file_code)
                    if w == 0:
                        MDM.send(RESPONCE+"Error in writing file"+EOF, 0)
                    else: 
                        MDM.send(RESPONCE+"File was successfully written"+EOF, 0)
                    continue
            # if fota not success, go to the next iteration(clear MDM buffer)
            if fota_process == 1: 
                fota_process = 0
                continue

            if (request.find(TRIPLE) != -1) and (len(request) == (len(TRIPLE)+6*3+10)):
                answer485 = socket485(request[len(TRIPLE):], 1)
                MDM.send(RESPONCE+answer485+EOF, 0)
                continue

            answer485 = socket485(request)
            MDM.send(RESPONCE+answer485+EOF, 0)
    if withsms == 1:
        sms_handler(DEVICE_ADDRESS, DEVICE_PASSWORD, DEVICE_A, 1)
    else:
        cmdAT('AT#REBOOT\r', 'OK', 2)

    

if __name__ == '__main__':
    MOD.watchdogEnable(900)
    try:
        EOF = '%end%'
        MESSAGE = 'message'
        RESPONCE = 'responce'
        RESTART = 'restart'
        FOTA = "fota_update"
        APPLY = 'apply'
        TRIPLE = 'triple'
        main()
    except Exception:
        cmdAT('+++', 'OK', 2)
        if smsinit() == 1:
            MOD.sleep(300)  #time for recieve sms
            sms_handler(DEVICE_ADDRESS, DEVICE_PASSWORD, DEVICE_A)
        #change boot script
        cmdAT('+++', 'OK', 2)
        MDM.send('AT#ESCRIPT?\r', 0)
        timeout = MOD.secCounter() + 5
        ok = MDM.receive(TIMEOUT_AT)
        while (((ok.find("bot.pyo") == -1) and (ok.find("bot2.pyo") == -1)) and MOD.secCounter() < timeout):
            ok = ok + MDM.receive(TIMEOUT_AT)
        if ((ok.find("bot.pyo") == -1) and (ok.find("bot2.pyo") == -1)):
            cmdAT('AT#REBOOT\r', 'OK', 2)
        if (ok.find("bot.pyo") == -1): file_name = "bot.pyo"
        else: file_name = "bot2.pyo"
        cmdAT('AT#ESCRIPT="'+file_name+'"\r', 'OK', 2)
        cmdAT('AT#REBOOT\r', 'OK', 2)



