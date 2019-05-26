import inspect
import traceback
import time
from streamElements import StreamElementsAPI
from db import Database as db

class NotEnoughArgsError(Exception):
    def __init__(self, num):
        self.message = f"Not enough arguments provided. Requires {f'{num} more argument' if num == 1 else f'{num} more arguments'}."

class BrieError(Exception):
    def __init__(self):
        self.message = "This is a generic Brie error."

class NotEnoughSPError(BrieError):
    def __init__(self, has, required):
        self.message = f"Not enough SP. You need {required - has} more."

class NotEnoughAffectionError(BrieError):
    def __init__(self, has, required):
        self.message = f"Not enough affection. You need {required - has} more."

class MissingItemError(BrieError):
    def __init__(self, item):
        self.message = f"You are missing the {item}."

class InvalidEntryError(BrieError):
    def __init__(self, entered):
        self.message = f"{entered} is not an item on the list."

class CommandHandler:
    def __init__(self, parent, prefix):
        self.parent = parent
        self.prefix = prefix

        # streamElements api implementation access
        self.se = StreamElementsAPI(parent.config.SE_ID, parent.config.JWT_ID, parent.loop)

        # command aliases. may be scrapped if not needed
        self._aliases = {
            "sd" : "shutdown"
        }

        # command cooldown dict
        # keys are command names, values are dicts
        #   keys of that dict are usernames, values are a timestamp
        self.cooldowns = {f[4:] : {} for f in dir(self) if f[:4] == "cmd_"}

    # To check for mod powers:
    # is_mod = await self.parent.is_mod(username)

    # To check for live status:
    # is_live = await self.parent.is_live()

    def send_message(self, msg, recipient=None):
        '''
        Simple wrapper to send a message.
        If a recipient is given, it needs to be in the format of a user name only. That will send a DM.
        '''
        if recipient is not None:
            self.parent.connection.privmsg(recipient, msg)
        else:
            self.parent.connection.privmsg(self.parent.target, msg)

    async def parse_for_command(self, user_tuple, message):
        '''
        Run a function defined within this class that matches the message
        '''
        if not message.startswith(self.prefix):
            return False

        user = user_tuple[0]
        user_id = user_tuple[1]

        message = message[1:] # remove the prefix
        if len(message) == 0: # if it was only a prefix, fail
            return False

        parts = message.split()
        name = parts[0]
        if name in self._aliases: # check if the word is an alias for a command
            name = self._aliases[name]

        # Trying to find the command function via the name determined above
        command = getattr(self, f"cmd_{name}", None)
        if command is None:
            return False

        # Check for cooldown timestamp failure
        # If the timestamp is in the past, success (if it's greater than now, fail)
        now = time.time()
        this_cooldown = self.cooldowns[name]
        if user in this_cooldown:
            if this_cooldown[user] > now:
                print("Cooldown failed.")
                return False

        parts.pop(0)
        params = inspect.signature(command).parameters.copy()
        kwargs = {}

        # Parse mentions for the mention_list
        # The final list is a list of user names without the @
        mentions = []
        for word in parts:
            if word.startswith('@') and len(word) > 1:
                mentions.append(word[1:])

        # These are function parameters. Put the specific names as a param for it to be sent.
        # user : user name
        # uid : user ID
        # args : rest of the message split into a list
        # message : rest of the message as a string
        # mention_list : list of user names mentioned by the message
        if params.pop("user", None):
            kwargs["user"] = user
        if params.pop("uid", None):
            kwargs["uid"] = user_id
        if params.pop("args", None): # if blank, this is an empty list
            kwargs["args"] = parts
        if params.pop("message", None): # if blank, this is an empty string
            kwargs["message"] = " ".join(parts)
        if params.pop("mention_list", None): # if blank, message mentions nobody
            kwargs["mention_list"] = mentions

        try:
            await command(**kwargs)
            #
            # reach this point if we succeed, do whatever you want here
            # Any fully successful command will set a new cooldown.
            this_cooldown[user] = now + 60.0

        except SystemExit:
            pass
        except BrieError as e: # Handling all failures
            print(user, "FAILED:", e.message)
        except NotEnoughArgsError as e: # Handling basic missing arg failures
            print(user, "MISSING ARGS:", e.message)
        except: # Default failures that are probably our fault
            print(f"Error in command {name}")
            traceback.print_exc()
            print("---\n")

    async def cmd_shutdown(self, user):
        '''
        Close the bot. Host only.
        '''
        if user == self.parent.host:
            self.parent.memory_config.save_data()
            print("Saving and quitting IRC...")
            await self.parent.aio_session.close()
            await self.se.aio_session.close()
            self.parent.connection.quit()

    async def cmd_tu(self, uid):
        '''
        test user create
        '''
        await db.create_new_user(uid)

    async def cmd_test_getpoints(self, user):
        '''
        test get points
        '''
        if user != self.parent.host:
            raise BrieError
        amount = await self.se.get_user_points(user)
        self.send_message(f"you have {amount} points")

    async def cmd_test_setpoints(self, user, args, mention_list):
        '''
        test set points of 1 user
        '''
        if user != self.parent.host:
            raise BrieError
        if len(args) < 2:
            raise NotEnoughArgsError(2 - len(args))

        # try your best to get the person of interest
        # justification for mention_list: args will not strip the '@' automatically so why not
        target = mention_list[0] if len(mention_list) != 0 else args[0]
        try:
            amount = int(args[1])
        except:
            raise BrieError
        new_amount = await self.se.set_user_points(target, amount)
        self.send_message(f"set {target} points to {new_amount}")

    async def cmd_help(self, user, args):
        '''
        Direct Message a user the help guide.
        '''
        # Left args in for specificity on commands for later, if wanted
        self.send_message("This is a test.")

    async def cmd_stats(self, user, args):
        '''
        Direct Message a user personal stats.
        '''
        # Left args in for specificity, if wanted
        pass

    async def cmd_bond(self, user, args):
        '''
        Display the bond leaderboard and happiness level.
        '''
        # Left args in for whatever reason
        pass

    async def cmd_feed(self, user, args):
        '''
        Feed a purchasable item. SP for the item is required. This helps hunger.
        '''
        if len(args) == 0:
            # Help text or a failure can go here
            raise NotEnoughArgsError(1)

        item = args[0]
        # Check for SP requirement
        pass

    async def cmd_gift(self, user, args):
        '''
        Gift a purchasable item. SP for the item is required. This gains affection.
        '''
        if len(args) == 0:
            # Help text or a failure
            raise NotEnoughArgsError(1)

        item = args[0]
        # Check for SP requirement
        pass

    async def cmd_buy(self, user, args):
        '''
        Buy an item, associated with a specific bonding activity permanently.
        '''
        if len(args) == 0:
            # Help text or a failure
            raise NotEnoughArgsError(1)

        item = args[0]
        # Check for SP
        pass

    async def cmd_headpat(self, user):
        '''
        Head pat bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_scratch(self, user):
        '''
        Scratch bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_hug(self, user):
        '''
        Hug bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_tickle(self, user):
        '''
        Tickle bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_nuzzle(self, user):
        '''
        Nuzzle bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_brush(self, user):
        '''
        Brush bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_massage(self, user):
        '''
        Massage bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_bellyrub(self, user):
        '''
        Belly rub bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_cuddle(self, user):
        '''
        Cuddling bonding activity
        '''
        # Check for item or other requirements based on the user
        pass

    async def cmd_holdhands(self, user):
        '''
        Hand holding bonding activity
        '''
        # Check for item or other requirements based on the user
        pass