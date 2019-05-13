import sys
import asyncio
import irc.bot
import irc.client
import irc.client_aio
import irc.strings
from conf import *

class TheBot(irc.client_aio.AioSimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        self.config = Conf(os.path.dirname(os.path.realpath(__file__))+"\\config.ini")
        self.memory_config = CSVMemory(os.path.dirname(os.path.realpath(__file__))+"\\memory.csv")
        self.memory = self.memory_config.persistentDict
        self.target = "#" + self.config.CHANNEL_NAME    # The name of the twitch irc channel
        
        # for asyncio, separate loop from irc connection loop thing
        self.eventloop = asyncio.get_event_loop()

        self.rollcall = False
        self.current_session_already_here = set()
        self.modlist = self.config.MOD_LIST
        self.host = self.config.HOST

    def on_welcome(self, connection, event):
        if irc.client.is_channel(self.target):
            connection.join(self.target)
            print("Connected to the Server...")
        else:
            print("Something is wrong and shit's broken")

    def on_join(self, connection, event):
        print("WE IN, BOYS")
        self.eventloop.create_task(self.saving_loop(connection))

    def on_disconnect(self, connection, event):
        self.eventloop.stop()
        sys.exit(0)
        
    def on_pubmsg(self, connection, event):
        #print(event.source.nick + ": " + event.arguments[0])
        user = event.source.nick.lower()
        params = event.arguments[0].split()
        if params[0] == "!attendance":
            if user in self.modlist:
                self.cmd_toggle_rollcall()
        elif params[0] == "!here":
            self.cmd_acknowledge_rollcall(user)
        elif params[0] == "!points":
            if len(params) == 1:
                self.cmd_checkpoints(user)
            else:
                self.cmd_checkpoints(params[1].strip("@"))
        elif params[0] == "!shutdown":
            self.cmd_shutdown(user)
        if user not in self.memory:
            self.memory[user] = (1,0)
        else:
            self.memory[user] = (self.memory[user][0] + 1, self.memory[user][1])

    async def saving_loop(self, connection):
        await asyncio.wait_for(asyncio.sleep(30), timeout=31, loop=self.eventloop)
        self.memory_config.save_data()
        await self.saving_loop(connection)


    def cmd_toggle_rollcall(self):
        if not(self.rollcall):
            self.rollcall = True
            self.current_session_already_here = set()
            self.connection.privmsg(self.target, "It's time to take attendance. Say !here to confirm.")
        else:
            self.rollcall = False
            self.connection.privmsg(self.target, "You are now late to class. No points for you.")
            self.memory_config.save_data()

    def cmd_acknowledge_rollcall(self, user):
        if self.rollcall:
            if user not in self.current_session_already_here:
                self.current_session_already_here.add(user)
                if user not in self.memory:
                    self.memory[user] = (1,1)
                else:
                    self.memory[user] = (self.memory[user][0], self.memory[user][1] + 1)

    def cmd_checkpoints(self, user):
        if user not in self.memory:
            self.connection.privmsg(self.target, user + " has never been to class on time and responded to roll call.")
        else:
            self.connection.privmsg(self.target, user + " has "+str(self.memory[user][1])+" points.")

    def cmd_shutdown(self, user):
        if user == self.host:
            self.memory_config.save_data()
            print("Saving and quitting IRC...")
            self.connection.quit()
            sys.exit(0)


        
bot = TheBot()
bot.connect("irc.chat.twitch.tv", 6667, bot.config.BOT_NAME, password=bot.config.AUTH_ID)
try:
    bot.start()
finally:
    bot.connection.disconnect()
    bot.reactor.loop.close()