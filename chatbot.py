import sys
import asyncio
import aiohttp
import logging
import irc.bot
import irc.client
import irc.client_aio
import irc.strings
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from conf import *
from commands import CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import STATE_STOPPED, STATE_RUNNING, STATE_PAUSED
from db import do_calc_happiness

sentry_logging = LoggingIntegration(
    level=logging.DEBUG, 
    event_level=logging.ERROR
)
sentry_sdk.init(
    dsn="https://bebaa1aa09624850be6de92149dd763a@sentry.everything.moe/1",
    integrations=[sentry_logging]
)

log = logging.getLogger("chatbot")
epicfilehandler = logging.FileHandler("chatbot.log", 'a', 'utf-8')
epicfilehandler.setFormatter(logging.Formatter("[%(asctime)s] [%(module)s] [%(levelname)s]: %(message)s"))
log.setLevel(logging.DEBUG)
log.addHandler(epicfilehandler)
log.addHandler(logging.StreamHandler(sys.stdout))

class TheBot(irc.client_aio.AioSimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        self.config = Conf(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini"))
        self.target = "#" + self.config.CHANNEL_NAME    # The name of the twitch irc channel
        self.channel_name = self.config.CHANNEL_NAME    # The display name of the twitch channel
        self.channel_id = ""                            # ID is saved as a string because JSON sends it that way
        self.host = self.config.HOST                    # The name of the host of the bot
        self.log = logging.getLogger("chatbot")         # Centralized logging
        
        # for twitch api stuff
        self.aio_session = None
        
        # shortcut to the async loop
        self.loop = self.connection.reactor.loop
        
        # we have to get the aiosession in an async way because deprecated methods
        self.loop.create_task(self.set_aio())

        # loop every once in a while to check if channel is live
        self.loop.create_task(self.is_live_loop())
        self.live = False

        # command handler stuff
        self.command_handler = CommandHandler(self, self.config.PREFIX)

        # hydration reminder
        self.loop.create_task(self.remind_drink_water())

        # scheduler stuff
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(do_calc_happiness, 'cron', hour='11', jitter=1800)
        self.scheduler.add_job(self.reconnect_loop, 'interval', hours=3)
        self.scheduler.start()
        
    async def set_aio(self):
        self.aio_session = aiohttp.ClientSession(headers={"Client-ID": self.config.CLIENT_ID, "Authorization": "Bearer %s" % self.config.JWT_ID, "User-Agent": "Brie/0.1 (+https://brie.everything.moe/)"})

    async def is_live_loop(self):
        '''
        Loop every 30 seconds and try to see if the defined channel is live.
        '''
        while True:
            await asyncio.sleep(30)
            if self.scheduler.state == STATE_STOPPED:
                # at this point we assume the scheduler stopped by shutdown command
                # so we kill everything explosively
                sys.exit(0)
            if not self.connection.is_connected():
                log.warning("Somehow, we lost the connection without knowing it.")
                await self.connection.connect("irc.chat.twitch.tv", 6667, self.config.BOT_NAME, password=self.config.AUTH_ID)
            if self.aio_session is None:
                continue
            try:
                status = await self.is_live()
                self.live = status
            except:
                log.exception(f"An exception occurred while updating the Live Status for {self.channel_id}")

    async def remind_drink_water(self):
        '''
        Quick and dirty reminder to drink water every 30 minutes.
        '''
        msg = "/me Squeak squeak! Ms. Bobber told me to come remind all her students to drink water and stay hydrated! A healthy mouse is a happy mouse! brieYay Let your fellow students know by posting bobberDrink !"
        while True:
            await asyncio.sleep(45*60)
            try:
                if self.live:
                    self.connection.privmsg(self.target, msg)
            except:
                log.exception("Failed to send hydration reminder in IRC chat")

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
            log.info("Connected to IRC.")
        else:
            print("Something is wrong and everything is broken (config is probably wrong)")

    def on_join(self, connection, event):
        '''
        Event triggered by IRC JOIN Messages, which anyone can cause (starting with yourself)
        '''
        # print("Someone joined the Twitch IRC Channel.")
        pass

    def on_disconnect(self, connection, event):
        '''
        Event run on disconnecting from IRC
        '''
        # Changed handling in main(). This should work with SystemExit Exception.
        log.info("Disconnected from IRC.")
        # sys.exit(0) # this force quits the program on disconnect

    # Sub module dispatcher should be this function (this is the main menu essentially)  
    def on_pubmsg(self, connection, event):
        '''
        Event run for every message sent in the IRC Channel
        '''
        name = event.source.nick.lower()
        message = event.arguments[0].strip()
        id = ""

        for d in event.tags: # irc, why did you decide this format was good?
            if d["key"] == "user-id":
                id = d["value"]

        user = (name, id)
        self.loop.create_task(
            self.command_handler.parse_for_command(user, message)
        )

    async def wait_for_request_window(self, url):
        '''
        sometimes we can get rate limited. wait for the rate limit window by doing this.
        also retry every 1 second on other errors (but only up to 30 times)
        '''
        attempt = True
        output = {}
        retries = 0
        while attempt and retries < 30:
            async with self.aio_session.get(url) as response:
                output = await response.json()
                if "status" in output:
                    log.warning(f"Got status {output['status']} error while requesting on {url}.")
                    if output["status"] == 429:
                        await asyncio.sleep(15)
                    else:
                        await asyncio.sleep(1)
                    retries += 1
                else:
                    attempt = False
        return output

    async def get_channel_id_by_name(self, specific_login = None):
        '''
        Use new twitch api to get a channel id by login name
        Pass a display name string to try a different channel name
        '''
        if specific_login is None:
            specific_login = self.channel_name

        url = f"https://api.twitch.tv/helix/users?login={specific_login}"
        json_response = await self.wait_for_request_window(url)
        channel_id = ""
        try:
            channel_id = json_response["data"][0]["id"]
        except:
            # this would fail if data was empty (it usually isnt)
            print("Channel ID retrieval via login name failed.")
            log.warning(f"Channel ID retrieval for login {specific_login} failed.")
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

        # empty returns from the streams api endpoint mean the channel is offline
        url = f"https://api.twitch.tv/helix/streams?user_id={channel_id}"
        json_response = await self.wait_for_request_window(url)
        return len(json_response["data"]) != 0

    async def is_mod(self, user_name = None, channel_id = None, user_id = None):
        '''
        Use a dank undocumented v5 twitch api method to find the mod badge
        But also use the new twitch api because IRC doesnt tell us the user id
        '''
        if user_id is None:
            user_id = await self.get_channel_id_by_name(specific_login=user_name)
        # fallback to main channel ID if none is specified
        if self.channel_id == "" and channel_id is None:
            self.channel_id = await self.get_channel_id_by_name()
            channel_id = self.channel_id
        elif channel_id is None:
            channel_id = self.channel_id

        url = f"https://api.twitch.tv/kraken/users/{user_id}/chat/channels/{channel_id}?api_version=5"
        # the response on api v5, is simply { ... : ... } with lists or dicts optionally embedded
        # it seems to always exist as far as i can tell
        json_response = await self.wait_for_request_window(url)

        badges = json_response.get("badges", [])
        for entry in badges:
            if entry["id"] in ("moderator", "broadcaster"):
                return True
        return False

    async def reconnect_loop(self):
        '''
        Just reconnect to IRC like we start out.
        This is meant to be run on a scheduler but can be called any time.
        '''
        log.info("Reconnecting to Twitch IRC to make sure connection remains alive.")
        await self.connection.connect("irc.chat.twitch.tv", 6667, self.config.BOT_NAME, password=self.config.AUTH_ID)

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
        log.info("Bot working to disconnect and close (initial stage).")
    finally:
        bot.connection.disconnect()
        bot.reactor.loop.close()
        log.info("Bot disconnected and closed (final stage).")

if __name__ == "__main__":
    main()

