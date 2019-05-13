import sys
import asyncio
import aiohttp
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
        self.channel_name = self.config.CHANNEL_NAME    # The display name of the twitch channel
        self.modlist = self.config.MOD_LIST             # List of people who are defined as mod
        self.host = self.config.HOST                    # The name of the host of the bot
        
        # for kraken (new twitch api) stuff
        self.aio_session = None
        
        # for asyncio, separate loop from irc connection loop thing
        self.eventloop = asyncio.get_event_loop()

        # command related variables
        self.rollcall = False
        self.current_session_already_here = set()
        
        # we have to get the aiosession in an async way because deprecated methods
        self.eventloop.create_task(self.set_aio())
        
        
    async def set_aio(self):
        self.aio_session = aiohttp.ClientSession(headers={"Client-ID": self.config.CLIENT_ID})
        
    def on_welcome(self, connection, event):
        '''
        Event run on entrance to the IRC
        '''
        if irc.client.is_channel(self.target):
            connection.join(self.target)
            print("Connected to the Server...")
        else:
            print("Something is wrong and everything is broken (config is probably wrong)")

    def on_join(self, connection, event):
        '''
        Event run on entrance to the IRC Channel
        '''
        print("WE IN, BOYS")
        self.eventloop.create_task(self.saving_loop(connection))

    def on_disconnect(self, connection, event):
        '''
        Event run on disconnecting from IRC
        '''
        self.eventloop.stop()
        sys.exit(0)
        
    def on_pubmsg(self, connection, event):
        '''
        Event run for every message sent in the IRC Channel
        '''
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
        elif params[0] == "!live":
            self.eventloop.create_task(self.send_is_live())
            
        # this puts the sender of the message into memory
        if user not in self.memory:
            self.memory[user] = (1,0)
        else:
            self.memory[user] = (self.memory[user][0] + 1, self.memory[user][1])

    async def saving_loop(self, connection):
        '''
        An async loop to save the memory to disk every 30 seconds
        '''
        await asyncio.wait_for(asyncio.sleep(30), timeout=31, loop=self.eventloop)
        self.memory_config.save_data()
        await self.saving_loop(connection)
        
    async def is_live(self):
        ''' 
        Use new twitch api in a scuffed way to find out if a channel is live
        '''
        async with self.aio_session.get("https://api.twitch.tv/helix/users?login=" + self.channel_name) as response:
            # this provides either a result or nothing
            # nothing is returned if the channel name doesnt exist
            # and by nothing I mean response.json() appears as {"data": [ ], "pagination": [ ]}
            json_response = await response.json()
            channel_id = ""
            try:
                channel_id = json_response["data"][0]["id"]
            except:
                # this would fail if data was empty (it usually isnt)
                print("Channel ID retrieval via login name failed.")
            
            async with self.aio_session.get("https://api.twitch.tv/helix/streams?user_id=" + channel_id) as response2:
                # and this provides nothing (in the same format above) if the channel is offline
                # i dont know why but that's how twitch works
                json_response2 = await response2.json()
                
                # print( len(json_response2["data"]) != 0 )
                return len(json_response2["data"]) != 0
            
    async def send_is_live(self):
        '''
        Send the is_live status to chat
        '''
        # i got bored and wanted to see if this was possible on one line
        output = f"{self.channel_name} is {await self.is_live() and '' or 'not '}live"
        
        self.connection.privmsg(self.target, output)

    def cmd_toggle_rollcall(self):
        '''
        Toggle the ability for chat to say they are here
        '''
        if not(self.rollcall):
            self.rollcall = True
            self.current_session_already_here = set()
            self.connection.privmsg(self.target, "It's time to take attendance. Say !here to confirm.")
        else:
            self.rollcall = False
            self.connection.privmsg(self.target, "You are now late to class. No points for you.")
            self.memory_config.save_data()

    def cmd_acknowledge_rollcall(self, user):
        '''
        Chat's ability to say they are present and get a point
        '''
        if self.rollcall:
            if user not in self.current_session_already_here:
                self.current_session_already_here.add(user)
                if user not in self.memory:
                    self.memory[user] = (1,1)
                else:
                    self.memory[user] = (self.memory[user][0], self.memory[user][1] + 1)

    def cmd_checkpoints(self, user):
        '''
        Check a given user's points
        '''
        if user not in self.memory:
            self.connection.privmsg(self.target, user + " has never been to class on time and responded to roll call.")
        else:
            self.connection.privmsg(self.target, user + " has "+str(self.memory[user][1])+" points.")

    def cmd_shutdown(self, user):
        '''
        Close the bot from chat/IRC
        '''
        if user == self.host:
            self.memory_config.save_data()
            print("Saving and quitting IRC...")
            self.connection.quit()
            sys.exit(0)


def main():
    '''
    Initializing the bot object, connecting to IRC, and running everything until it eventually dies
    '''
    bot = TheBot()
    bot.connect("irc.chat.twitch.tv", 6667, bot.config.BOT_NAME, password=bot.config.AUTH_ID)
    try:
        bot.start()
    finally:
        bot.connection.disconnect()
        bot.reactor.loop.close()
if __name__ == "__main__":
    main()