import configparser
import os
import shutil


class Conf:
    '''
    Load configuration from a set ini file so we dont have to hardcode auth keys
    '''
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

        # these get methods let you fall back on errors or missing stuff, so its good
        # we may want to retrieve the mod list from somewhere other than a defined ini list
        self.AUTH_ID = config.get("Password", "Token", fallback=Fallbacks.AUTH_ID)
        self.JWT_ID = config.get("Password", "SE_JWT_Token", fallback=Fallbacks.JWT_ID)
        self.CLIENT_ID = config.get("Password", "Client ID", fallback=Fallbacks.CLIENT_ID)
        self.SE_ID = config.get("Password", "SE_ID", fallback=Fallbacks.SE_ID)

        self.BOT_NAME = config.get("Names", "Bot Nickname", fallback=Fallbacks.BOT_NAME)
        self.HOST = config.get("Names", "Host", fallback=Fallbacks.HOST).lower()

        self.CHANNEL_NAME = config.get("Channel", "Name", fallback=Fallbacks.CHANNEL_NAME)
        
        self.PREFIX = config.get("Commands", "Prefix", fallback=Fallbacks.PREFIX)



class Fallbacks:  # these will only get used if the user leaves the config.ini existant but really messes something up... everything breaks if they get used.
    AUTH_ID = "mission failed"
    JWT_ID = "bad streamelements token"
    SE_ID = "bad streamelements account id"
    BOT_NAME = "incorrect_configuration"
    CLIENT_ID = "got oofed"
    CHANNEL_NAME = "shroud"
    HOST = "0fallback"
    PREFIX = "!"
