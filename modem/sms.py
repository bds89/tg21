import MDM
import SER
import MOD
from crc16 import crc16, check_crc16

def cmdAT(cmd, result, time_out, recursive_n = 0):
    if recursive_n > 2: MOD.sleep(30)
    MDM.send(cmd, 0)
    timeout = MOD.secCounter() + time_out
    res = MDM.receive(10)
    while (res.find(result) == -1 and MOD.secCounter() < timeout):
        res = res + MDM.receive(10)
    if (res.find(result) == -1): 
        if cmd == '+++':
            if cmdAT('AT\r', 'OK', 1) != "":
                return "OK"
            else: cmdAT('+++', 'OK', time_out+1, recursive_n+1)
        return ""
    else: return res

def smsinit():
    if cmdAT('AT+CMGF=1\r', 'OK', 2) != "":
        if cmdAT('AT+CNMI=0,1\r', 'OK', 2) != "":
            return 1
    return 0

def energy_to_text(responce, A):
    energyDict = {}
    energyDict.update({"Active direct":responce[1:5]})
    energyDict.update({"Active reverse":responce[5:9]})
    energyDict.update({"Reactive direct":responce[9:13]})
    energyDict.update({"Reactive reverse":responce[13:17]})
    text = ""
    energyDictTxt = {}

    for key, value in energyDict.items():
        energy_dec = 0
        for i in value:
            energy_dec = energy_dec * 256 + ord(i)
            energyDictTxt.update({key:str(energy_dec/(2*A))})
    text = text + "Active direct: "+energyDictTxt["Active direct"]+"\r\n\r\n"+\
                    "Reactive direct: "+energyDictTxt["Reactive direct"]+"\r\n"+\
                        "Active reverse: "+energyDictTxt["Active reverse"]+"\r\n"+\
                            "Reactive reverse: "+energyDictTxt["Reactive reverse"]+"\r\n"
    return text

def sendSMS(phone, text):
    if cmdAT('AT+CMGS="'+phone+'",145\r', chr(13)+chr(10)+chr(62)+chr(32), 5) != "":
        cmdAT(text, "", 1)
        cmdAT(chr((0x1A)), '+CMGS:', 5)
        return
    else:
        return

def internet(arg):
    try:
        f = open("internet.txt", "w")
        f.write(arg)
        f.flush()
        f.close()
    except IOError:
        1==1

def sms_handler(address, password, A, loop = 0):
    while (1==1):
        if (cmdAT('+++', 'OK', 3) == ""): cmdAT('AT\r', 'OK', 2)
        cmdAT('AT+CPBS?\r', '+CPBS:', 10)
        smslist = cmdAT('AT+CMGL="ALL"\r', 'OK', 5)
        smslist = smslist.split('\n')
        listIndex = []
        smsDict = {}
        key = ""
        for string in smslist:
            if(string.find("+CMGL:") != -1):    #find the index of each sms
                start = string.find(":")
                end = string.find(",")
                myindex = string[(start+1):end]
                myindex = myindex.strip()
                listIndex.append(myindex)   
                if(string.find("+7") != -1):    #find the phone of each sms
                    start = string.find("+7")
                    end = string.find('"', start)
                    phone = string[start:end]
                    phone = phone.strip()
                    key = phone
            if ((string.find("energy") != -1 or string.find("Energy") != -1 or string.find("ENERGY") != -1) and (key != "")):    #find the command of each sms
                smsDict.update({key:"energy"})
                key = ""
            elif ((string.find("reboot") != -1 or string.find("Reboot") != -1 or string.find("REBOOT") != -1) and (key != "")):    #find the command of each sms
                smsDict.update({key:"reboot"})
                key = ""
            elif ((string.find("interneton") != -1 or string.find("Interneton") != -1 or string.find("INTERNETON") != -1) and (key != "")):    #find the command of each sms
                smsDict.update({key:"interneton"})
                key = ""
            elif ((string.find("internetoff") != -1 or string.find("Internetoff") != -1 or string.find("INTERNETOFF") != -1) and (key != "")):    #find the command of each sms
                smsDict.update({key:"internetoff"})
                key = ""
            else: continue
        if listIndex == []:
            if loop == 0: return
            else: 
                MOD.sleep(10)
                continue
        #delete all sms
        for index in listIndex:
            cmdAT('AT+CMGD='+index+'\r', 'OK', 5)
        if cmdAT('AT+CMGL="ALL"\r', '+CMGL:', 1) != "": return
        
        # make requests
        for phone, command in smsDict.items():
            if command == "interneton":
                internet("on")
            if command == "internetoff":
                internet("off")
            if command == "energy":
                SER.read() #clear buffer
                request = chr(address)+chr(0x01)+password
                access_request = crc16(request)
                SER.send(access_request)
                res = ""
                timeout = MOD.secCounter() + 5
                res = SER.read()
                while((check_crc16(res) == 0) and (MOD.secCounter() < timeout)):
                    MOD.sleep(10)
                    res = res + SER.read()
                if check_crc16(res) == 0:
                    sendSMS(phone, "No responce")
                    if loop == 0: return
                    else: continue
                if res[:2] != (chr(address)+chr(0x00)):
                    sendSMS(phone, "Bad responce")
                    return
                    
                MOD.sleep(10)
                #make main request
                request = chr(address)+chr(0x05)+chr(0x00)+chr(0x01)
                request_main = crc16(request)
                SER.send(request_main)
                res = ""
                timeout = MOD.secCounter() + 5
                res = SER.read()
                while((check_crc16(res) == 0) and (MOD.secCounter() < timeout)):
                    MOD.sleep(10)
                    res = res + SER.read()
                if (check_crc16(res) == 0):
                    sendSMS(phone, "No responce")
                    if loop == 0: return
                    else: continue
                sendSMS(phone, energy_to_text(res, A))
            if command == "reboot":
                cmdAT('AT#REBOOT\r', 'OK', 5)
        if loop == 0: return
        else: 
            MOD.sleep(10)
            continue
    


