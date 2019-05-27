import sys
import asyncio
import aiohttp
import irc.bot
import irc.client
import irc.client_aio
import irc.strings
import sentry_sdk
from conf import *
from commands import CommandHandler

sentry_sdk.init("http://bebaa1aa09624850be6de92149dd763a@localhost/1")

class TheBot(irc.client_aio.AioSimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        self.config = Conf(os.path.dirname(os.path.realpath(__file__))+"\\config.ini")
        self.memory_config = CSVMemory(os.path.dirname(os.path.realpath(__file__))+"\\memory.csv")
        self.memory = self.memory_config.persistentDict
        self.target = "#" + self.config.CHANNEL_NAME    # The name of the twitch irc channel
        self.channel_name = self.config.CHANNEL_NAME    # The display name of the twitch channel
        self.channel_id = ""                            # ID is saved as a string because JSON sends it that way
        self.host = self.config.HOST                    # The name of the host of the bot
        
        # for twitch api stuff
        self.aio_session = None
        
        # shortcut to the async loop
        self.loop = self.connection.reactor.loop
        
        # we have to get the aiosession in an async way because deprecated methods
        self.loop.create_task(self.set_aio())

        # command handler stuff
        self.command_handler = CommandHandler(self, self.config.PREFIX)
        
    async def set_aio(self):
        self.aio_session = aiohttp.ClientSession(headers={"Client-ID": self.config.CLIENT_ID, "Authorization": "Bearer %s" % self.config.JWT_ID, "User-Agent": "Brie/0.1 (+https://brie.everything.moe/)"})

    def on_welcome(self, connection, event):
        '''
        Event run on entrance to the IRC
        '''
        if irc.client.is_channel(self.target):
            connection.cap("REQ", ":twitch.tv/membership")
            connection.cap("REQ", ":twitch.tv/tags")
            connection.cap("REQ", ":twitch.tv/commands")
            connection.join(self.target)
            print("Connected to the Server...")
        else:
            print("Something is wrong and everything is broken (config is probably wrong)")

    def on_join(self, connection, event):
        '''
        Event run on entrance to the IRC Channel
        '''
        print("WE IN, BOYS")
        self.loop.create_task(self.saving_loop())

    def on_disconnect(self, connection, event):
        '''
        Event run on disconnecting from IRC
        '''
        # Changed handling in main(). This should work with SystemExit Exception.
        sys.exit(0)

    # Sub module dispatcher should be this function (this is the main menu essentially)  
    def on_pubmsg(self, connection, event):
        '''
        Event run for every message sent in the IRC Channel
        '''
        # print(event.source.nick + ": " + event.arguments[0])
        name = event.source.nick.lower()
        message = event.arguments[0]
        id = ""

        for d in event.tags: # irc, why did you decide this format was good?
            if d["key"] == "user-id":
                id = d["value"]

        user = (name, id)
        self.loop.create_task(
            self.command_handler.parse_for_command(user, message)
        )

    async def saving_loop(self): # is there a better way to do this?
        '''
        An async loop to save the memory to disk every 30 seconds
        '''
        while True:
            await asyncio.sleep(30)
            self.memory_config.save_data()

    async def get_channel_id_by_name(self, specific_login = None):
        '''
        Use new twitch api to get a channel id by login name
        Pass a display name string to try a different channel name
        '''
        if specific_login is None:
            specific_login = self.channel_name

        async with self.aio_session.get("https://api.twitch.tv/helix/users?login=" + specific_login) as response:
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
            return channel_id
        
    async def is_live(self, channel_id = None):
        '''
        Use new twitch api in a scuffed way to find out if a channel is live
        Pass a channel id string to try a specific channel id
        '''
        # fallback to main channel ID if none is specified
        if self.channel_id == "" and channel_id is None:
            self.channel_id = await self.get_channel_id_by_name()
            channel_id = self.channel_id
        elif channel_id is None:
            channel_id = self.channel_id

        async with self.aio_session.get("https://api.twitch.tv/helix/streams?user_id=" + channel_id) as response:
            # and this provides nothing (in the payload format) if the channel is offline
            # i dont know why but that's how twitch works
            json_response = await response.json()

            return len(json_response["data"]) != 0
            
    async def send_is_live(self):
        '''
        Send the is_live status to chat
        '''
        # i got bored and wanted to see if this was possible on one line
        output = f"{self.channel_name} is {'' if await self.is_live() else 'not '}live"
        self.connection.privmsg(self.target, output)

    async def is_mod(self, user, channel_id = None):
        '''
        Use a dank undocumented v5 twitch api method to find the mod badge
        But also use the new twitch api because IRC doesnt tell us the user id
        '''
        user_id = await self.get_channel_id_by_name(specific_login=user)
        # fallback to main channel ID if none is specified
        if self.channel_id == "" and channel_id is None:
            self.channel_id = await self.get_channel_id_by_name()
            channel_id = self.channel_id
        elif channel_id is None:
            channel_id = self.channel_id

        async with self.aio_session.get(f"https://api.twitch.tv/kraken/users/{user_id}/chat/channels/{channel_id}?api_version=5") as response:
            # the response on api v5, is simply { ... : ... } with lists or dicts optionally embedded
            # it seems to always exist as far as i can tell
            json_response = await response.json()

            badges = json_response.get("badges", [])
            for entry in badges:
                if entry["id"] in ("moderator", "broadcaster"):
                    return True
            return False

    async def send_is_mod(self, user):
        '''
        Send the is_mod status of a user to chat
        '''
        # round 2 of bored one liners
        self.connection.privmsg(self.target, f"{user} is {'' if await self.is_mod(user) else 'not '}a mod")

def main():
    '''
    Initializing the bot object, connecting to IRC, and running everything until it eventually dies
    '''
    bot = TheBot()
    bot.connect("irc.chat.twitch.tv", 6667, bot.config.BOT_NAME, password=bot.config.AUTH_ID)
    try:
        bot.start()
    except SystemExit:
        for t in asyncio.Task.all_tasks():
            t.cancel()
        bot.reactor.loop.run_until_complete(bot.reactor.loop.shutdown_asyncgens())
        bot.reactor.loop.stop()
    finally:
        bot.connection.disconnect()
        bot.reactor.loop.close()
if __name__ == "__main__":
    main()