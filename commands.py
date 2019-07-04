import inspect
import traceback
import time
import random
import logging
import json
from streamElements import StreamElementsAPI
from db import Database as db
from db import BRIES_ID
from bonds import BondHandler, NoMoreAttemptsError, MissingItemError, BondFailedError
from storefront import StoreHandler, NoItemError, NotEnoughSPError, AlreadyOwnedError, FreeFeedUsed, OutOfSeasonError

class NotEnoughArgsError(Exception):
    def __init__(self, num):
        self.message = f"Not enough arguments provided. Requires {f'{num} more argument' if num == 1 else f'{num} more arguments'}."

class BrieError(Exception):
    def __init__(self, message="This is a generic Brie error."):
        self.message = message

class NotEnoughAffectionError(BrieError):
    def __init__(self, has, required):
        self.message = f"Not enough affection. You need {required - has} more."

class InvalidEntryError(BrieError):
    def __init__(self, entered):
        self.message = f"{entered} is not an item on the list."

class CommandHandler:
    def __init__(self, parent, prefix):
        self.log = logging.getLogger("chatbot")
        self.parent = parent
        self.prefix = prefix
        self.dialogue = {}

        path = "dialogue.json"
        try:
            with open(path) as f:
                self.dialogue = json.load(f)
        except:
            self.log.exception("Failed to load dialogue JSON.")

        # streamElements api implementation access
        self.se = StreamElementsAPI(parent.config.SE_ID, parent.config.JWT_ID, parent.loop)

        # command aliases. may be scrapped if not needed
        self._aliases = {
            "sd" : "shutdown"
        }

        self.allow_online = False

        # command cooldown dict
        # keys are command names, values are dicts
        #   keys of that dict are usernames, values are a timestamp
        self.cooldowns = {f[4:] : {} for f in dir(self) if f[:4] == "cmd_"}

        # db cache for user accounts
        # simply a set of all user ids
        self.existing_users = set()
        parent.loop.create_task(self.reload_existing_users())

    # To check for mod powers:
    # is_mod = await self.parent.is_mod(username)

    # To check for live status:
    # is_live = await self.parent.is_live()

    def send_message(self, msg, recipient=None):
        '''
        Simple wrapper to send a message.
        If a recipient is given, it needs to be in the format of a user name only. That will send a DM.
        '''
        if msg == "" or msg is None:
            msg = "."
        if recipient is not None:
            self.parent.connection.privmsg(recipient, msg)
        else:
            self.parent.connection.privmsg(self.parent.target, msg)

    async def reload_existing_users(self):
        '''
        Reset the cached list of users available.
        This is just to reduce the need for repeatedly pinging the db to see if a user exists.
        '''
        result = await db.get_column("user_id")
        for i in range(len(result)):
            result[i] = str(result[i])
        self.existing_users = set(result)

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

        self.log.info(user + " ("+user_id+"): " + message)

        parts = message.split()
        name = parts[0]
        if name in self._aliases: # check if the word is an alias for a command
            name = self._aliases[name]

        # Trying to find the command function via the name determined above
        command = getattr(self, f"cmd_{name}", None)
        if command is None:
            return False

        # Check if the channel is online.
        # We want this bot to deny all commands if the bot is online.
        if self.parent.live and not self.allow_online and name != "toggleonline":
            self.log.info(f"{user} tried to execute command {name} but the channel is online.")
            return False

        # Check for cooldown timestamp failure
        # If the timestamp is in the past, success (if it's greater than now, fail)
        now = time.time()
        this_cooldown = self.cooldowns[name]
        if user in this_cooldown:
            if this_cooldown[user] > now:
                self.log.info(f"{user} tried to execute command {name} but the cooldown hasn't ended.")
                return False

        # Check to see that the user has info stored in the db for the game
        # The first check is to the cache.
        # If the check fails, update the list and check. If this fails, make a new entry.
        if user_id not in self.existing_users:
            await self.reload_existing_users()
            if user_id not in self.existing_users:
                self.log.info(f"Creating new user table entry for {user} ({user_id})")
                await db.create_new_user(user_id, user)
                self.existing_users.add(user_id)

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
            result = await command(**kwargs)
            #
            # reach this point if we succeed, do whatever you want here
            # Any fully successful command will set a new cooldown.
            this_cooldown[user] = now + 30.0
            if result is None or result == True: # catch commands which dont return anything
                self.log.info(f"{user} executed command {name} successfully.")
            elif result is not None and result != False:
                self.log.info(f"{user} executed command {name} successfully with status: {result}")
            else:
                self.log.info(f"{user} attempted to execute command {name} but was denied.")

        except SystemExit:
            pass
        except BrieError as e: # Handling all failures
            # print(user, "FAILED:", e.message)
            self.log.info(f"{user} failed command {name}: {e.message}")
        except NotEnoughArgsError as e: # Handling basic missing arg failures
            # print(user, "MISSING ARGS:", e.message)
            self.log.info(f"{user} failed command {name}: {e.message}")
        except: # Default failures that are probably our fault
            self.log.exception(f"{user} tried to execute command {name} but a critical internal error occurred.")
            print(f"Error in command {name}")
            traceback.print_exc()
            print("---\n")
        finally:
            return True

    def __choose_line(self, arr):
        '''
        Returns a random string from a list 
        of given strings
        '''
        i = random.randint(0, len(arr)-1)
        return arr[i]

    async def cmd_shutdown(self, user):
        '''
        Close the bot. Host only.
        '''
        if user == self.parent.host:
            print("Saving and quitting IRC...")
            await self.parent.aio_session.close()
            await self.se.aio_session.close()
            self.parent.connection.quit()
            return True
        return False

    async def cmd_toggleonline(self, user, uid):
        '''
        Toggle the requirement for the bot to be online from chat.
        Mod only.
        '''
        if await self.parent.is_mod(user_id=uid):
            self.allow_online = not self.allow_online
            self.send_message("Listening while streaming!" if self.allow_online else "No longer listening while streaming.")
            return True
        return False

    async def cmd_help(self, user, args):
        '''
        Direct Message a user the help guide.
        '''
        # Left args in for specificity on commands for later, if wanted
        self.send_message("Read how to play the game here! https://brie.everything.moe")
        return True

    async def cmd_stats(self, user, uid, args):
        '''
        Direct Message a user personal stats.
        '''
        # Left args in for specificity, if wanted
        
        affection = await db.get_value(uid, "affection")
        bond_level = await db.get_value(uid, "bond_level")
        stat_str = f"{user}\'s stats with me are: {affection}% affection, {bond_level} bond level!"

        self.send_message(stat_str)
        return True

    async def cmd_topbonds(self, user, args):
        '''
        Display the bond leaderboard and happiness level.
        '''
        # Left args in for whatever reason
        
        leaders = await db.get_top_rows_by_column_exclude_uid("username", "bond_level", 5, BRIES_ID)
        brie_happiness = await db.get_brie_happiness()
        brie_hapLevel = brie_happiness//100 # floored integer
        if len(leaders) >= 3:
            runner_ups = f'But {", ".join(leaders[1:-1])} and {leaders[-1]} are special, too! '
        elif len(leaders) == 2:
            runner_ups = f"But {leaders[-1]} is special, too! "
        else:
            runner_ups = ""
        leaderboard_str = f"I love {leaders[0]} the most! {runner_ups}My current happiness level is {brie_hapLevel}!"

        self.send_message(leaderboard_str)
        return True

    async def cmd_feed(self, user, uid, args):
        '''
        Feed a purchasable item. SP for the item is required. This helps hunger.
        '''
        if len(args) == 0:
            # Help text or a failure can go here
            raise NotEnoughArgsError(1)

        item = args[0].lower()
        # Check for SP requirement
        try:
            user_sp = await self.se.get_user_points(user)
            cost = await StoreHandler.try_feed(uid, user_sp, item)
            await self.se.set_user_points(user, -cost)
            self.send_message(self.__choose_line(self.dialogue["food"][item]))
        except NoItemError as e:
            self.send_message(self.dialogue["info"]["cantbuyfood"])
            raise BrieError(e.message)
        except OutOfSeasonError as e:
            self.send_message(self.dialogue["info"]["noseason"])
            raise BrieError(e.message)
        except NotEnoughSPError as e:
            self.send_message(self.dialogue["info"]["nosp"])
            raise BrieError(e.message)
        except FreeFeedUsed as e:
            self.send_message(self.dialogue["info"]["nofreefeed"])
            raise BrieError(e.message)
        except:
            raise
        return True

    async def cmd_gift(self, user, uid, args):
        '''
        Gift a purchasable item. SP for the item is required. This gains affection.
        '''
        if len(args) == 0:
            # Help text or a failure
            raise NotEnoughArgsError(1)

        item = args[0]
        # Check for SP requirement
        try:
            user_sp = await self.se.get_user_points(user)
            puzzle = await StoreHandler.try_gift(uid, user_sp, item)
            await self.se.set_user_points(user, -puzzle["cost"])
            self.send_message(self.dialogue["gifts"]["puzzle"][puzzle["reward"]])
        except NoItemError as e:
            self.send_message(self.dialogue["info"]["cantbuygift"])
            raise BrieError(e.message)
        except NotEnoughSPError as e:
            self.send_message(self.dialogue["info"]["nosp"])
            raise BrieError(e.message)
        except:
            raise
        return True

    async def cmd_buy(self, user, uid, args):
        '''
        Buy an item, associated with a specific bonding activity permanently.
        '''
        if len(args) == 0:
            # Help text or a failure
            raise NotEnoughArgsError(1)

        item = args[0]
        # Check for SP
        try:
            user_sp = await self.se.get_user_points(user)
            cost = await StoreHandler.try_buy(uid, user_sp, item)
            await self.se.set_user_points(user, -cost)
            self.send_message(f"Squeak! (Here's your {item})!")
        except NoItemError as e:
            self.send_message(self.dialogue["info"]["cantbuyitem"])
            raise BrieError(e.message)
        except NotEnoughSPError as e:
            self.send_message(self.dialogue["info"]["nosp"])
            raise BrieError(e.message)
        except AlreadyOwnedError as e:
            self.send_message(self.dialogue["info"]["alreadyown"])
            raise BrieError(e.message)
        except:
            raise
        return True

    async def __bond_command_internal(self, user, uid, bond_name):
        '''
        Private method to run the process of every bond command so code doesn't repeat over and over
        '''
        bond = BondHandler.bond_list[bond_name]
        try:
            await BondHandler.try_bond(uid, bond)
            self.send_message(self.__choose_line(self.dialogue["bonding"][bond_name]["success"]))
            return True
        except NoMoreAttemptsError:
            self.send_message(self.dialogue["info"]["noattempts"])
            raise BrieError("Out of bond attempts.")
        except MissingItemError as e:
            self.send_message(self.dialogue["info"][f"no{bond['item']}"])
            raise BrieError(e.message)
        except BondFailedError:
            self.send_message(self.__choose_line(self.dialogue["bonding"][bond_name]["failure"]))
            return "Bond failed."
        except:
            raise

    async def cmd_headpat(self, user, uid):
        '''
        Head pat bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "headpat")

    async def cmd_scratch(self, user, uid):
        '''
        Scratch bonding activity
        Requires "scratcher"
        '''
        return await self.__bond_command_internal(user, uid, "scratch")

    async def cmd_hug(self, user, uid):
        '''
        Hug bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "hug")

    async def cmd_tickle(self, user, uid):
        '''
        Tickle bonding activity
        Requires "feather"
        '''
        return await self.__bond_command_internal(user, uid, "tickle")

    async def cmd_nuzzle(self, user, uid):
        '''
        Nuzzle bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "nuzzle")

    async def cmd_brush(self, user, uid):
        '''
        Brush bonding activity
        Requires "brush"
        '''
        return await self.__bond_command_internal(user, uid, "brush")

    async def cmd_massage(self, user, uid):
        '''
        Massage bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "massage")

    async def cmd_bellyrub(self, user, uid):
        '''
        Belly rub bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "bellyrub")

    async def cmd_cuddle(self, user, uid):
        '''
        Cuddling bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "cuddle")

    async def cmd_holdhands(self, user, uid):
        '''
        Hand holding bonding activity
        '''
        return await self.__bond_command_internal(user, uid, "holdhands")
