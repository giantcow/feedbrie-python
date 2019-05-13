import configparser
import os
import shutil


class Conf:
    def __init__(self, conf):
        self.options = conf
        config = configparser.ConfigParser(interpolation=None)

        if not config.read(conf, encoding='utf-8'):
            print(
                "I had to remake the config file from default. Please check the config and restart once the proper settings have been changed.")
            print("The config should exist here: " + self.options)
            try:
                shutil.copy(os.path.dirname(self.options) + "\\example_config.ini", self.options)
            except:
                print("Well... Somehow the example I was copying from is also gone. You're in a bad spot.")
            os._exit(1)

        config.read(conf, encoding='utf-8')

        self.AUTH_ID = config.get("Password", "Token", fallback=Fallbacks.AUTH_ID)
        self.BOT_NAME = config.get("Names", "Bot Nickname", fallback=Fallbacks.BOT_NAME)
        self.CHANNEL_NAME = config.get("Channel", "Name", fallback=Fallbacks.CHANNEL_NAME)
        self.MOD_LIST = config.get("Names", "Mod List", fallback=Fallbacks.MOD_LIST).split()
        for i in range(len(self.MOD_LIST)):
            self.MOD_LIST[i] = self.MOD_LIST[i].lower()
        self.HOST = config.get("Names", "Host", fallback=Fallbacks.HOST).lower()



class Fallbacks:  # these will only get used if the user leaves the config.ini existant but really messes something up... everything breaks if they get used.
    AUTH_ID = "mission failed"
    BOT_NAME = "incorrect_configuration"
    CHANNEL_NAME = "shroud"
    MOD_LIST = ["0", "1", "2"]
    HOST = "0fallback"


class CSVMemory:
    def __init__(self, conf):
        self.config_dir = conf
        self.the_file = self._load_file(self.config_dir)
        self.persistentDict = {}


        for line in self.the_file:
            try:
                info = line.split(",")
                self.persistentDict[info[0]] = (int(info[1]),int(info[2]))
                # info is made of [user name, all time messages, points]
                # the middle stat is for your own amusement
            except:
                pass
        self.the_file.close()

    def save_data(self):
        the_file = self._load_file(self.config_dir, option="w")
        finalstr = "name,all_time_messages,early_activity\n"
        for k,v in self.persistentDict.items():
            u = [str(o) for o in v]
            finalstr = finalstr + k + "," + ",".join(u) + "\n"
        the_file.write(finalstr)
        the_file.close()


    def _load_file(self, dir, option="r"):
        try:
            the_file = open(dir, option)
            return the_file
        except:
            try:
                print(
                    "I had to remake the memory file from default. Please check everything and restart once the proper settings have been changed.")
                print("The memory should exist here: " + dir)
                shutil.copy(os.path.dirname(dir) + "\\example_memory.csv", dir)

            except:
                print("Well... Somehow the example I was copying from is also gone. You're in a bad spot.")
            os._exit(2)