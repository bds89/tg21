import MOD
import MDM
import SER
from crc16 import check_crc16

TIMEOUT_AT = 10
TIMEOUT_NET = 15
TIMEOUT_485 = 5

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

def init(
    SPEED485, 
    OPERATORS,
    OP_SYMBOLS,
    AP,
    USER,
    PASSWORD,
    ):

    SER.set_speed(SPEED485)
    #Choose operator
    MDM.send('AT+COPS?\r', 0)
    oper = MDM.receive(TIMEOUT_AT)
    oper = oper[oper.find('"'):oper.rfind('"')]
    max = 0
    max_name = ""
    for op_name, op_symbols in OP_SYMBOLS.items():
        correct = 0
        for letter in op_symbols:
            if oper.find(letter) != -1: correct = correct + 1
        if correct > max:
            max = correct
            max_name = op_name
    operator = max_name

    for operator_from_list in OPERATORS:
        if operator == "": operator = operator_from_list
        #APN set
        if (cmdAT('AT+CGDCONT=1,"IP","'+AP[operator]+'"\r', 'OK', 2) == 0):
            cmdAT('AT#REBOOT\r', 'OK', 2)

        #Check network registration
        MDM.send('at+creg?\r', 0)
        ok = MDM.receive(TIMEOUT_AT)
        if (ok.find ('OK') == -1 and ok.find ('0,1') == -1):
            MDM.send('at+creg=0\r', 0)
            timeout = MOD.secCounter() + 60
            ok = MDM.receive(TIMEOUT_NET)
            while ((ok.find ('OK') == -1 and ok.find ('0,1') == -1) and MOD.secCounter() < timeout):
                MOD.sleep(2)
                MDM.send('at+creg?\r', 0)
                ok = MDM.receive(TIMEOUT_AT)
            if (ok.find ('OK') == -1 and ok.find ('0,1') == -1):
                cmdAT('AT#REBOOT\r', 'OK', 2)

        #Activate context 1
        MOD.sleep(50)
        MDM.send('AT#SGACT=1,1,'+USER[operator]+','+PASSWORD[operator]+'\r', 0)
        ok = ""
        timeout = MOD.secCounter() + 60
        ok = MDM.receive(TIMEOUT_NET)
        while (len(ok) == 0 and MOD.secCounter() < timeout):
            ok = ok + MDM.receive(TIMEOUT_NET)
        if (ok.find('OK') == -1):
            if operator == "mts":
                cmdAT('AT#REBOOT\r', 'OK', 2)
            else:
                operator = ""
                continue
        else:
            break

    #signal
    MDM.send('AT+CSQ\r', 0)
    try:
        res = MDM.receive(TIMEOUT_AT)
        start = res.find('+CSQ:')+len('+CSQ: ')
        end = res.find(',', start)
        signal = res[start:end]
    except Exception:
        signal = 'unknown'
    return (operator, signal)