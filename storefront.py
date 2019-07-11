import json
import logging
import random
import datetime
from db import Database as db

log = logging.getLogger("storefront")
epicfilehandler = logging.FileHandler("store.log")
epicfilehandler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.setLevel(logging.DEBUG)
log.addHandler(epicfilehandler)

class NotEnoughSPError(Exception):
    def __init__(self):
        self.message = "Not enough SP to purchase item."

class NoItemError(Exception):
    def __init__(self):
        self.message = "That is not a store item."

class OutOfSeasonError(Exception):
    def __init__(self):
        self.message = "That is out of season."

class FreeFeedUsed(Exception):
    def __init__(self):
        self.message = "You already used your free cracker."

class AlreadyOwnedError(Exception):
    def __init__(self):
        self.message = "You already own that item."

class StoreLoader:
    @staticmethod
    def load_store(path="store.json"):
        '''
        Load store from a JSON file
        '''
        data = {}
        try:
            with open(path) as f:
                data = json.load(f)
        except:
            log.exception("Failed to load Bonds JSON.")
        return data

class StoreHandler:

    store_list = StoreLoader.load_store()

    @staticmethod
    def __get_season():
        thisMonth = datetime.datetime.now().month
        if 3 <= thisMonth <= 5:
            return "spring"
        elif 6 <= thisMonth <= 8:
            return "summer"
        elif 9 <= thisMonth <= 11:
            return "fall"
        return "winter"
    
    @staticmethod
    def reload_store(path="store.json"):
        '''
        Reload store from disk
        '''
        StoreHandler.store_list = StoreLoader.load_store(path)
        log.info("Reloading store from JSON.")
    
    @staticmethod
    def gamble_puzzle(item, com, unc):
        '''
        Takes odds for common, uncommon, and rare(implicit) win
        and outputs appropriate AP to reward
        '''
        reward = StoreHandler.store_list["gifts"][item]["reward"]
        rand = random.randint(1,100)
        if 0 < rand <= com:
            return {"type": "common", "value": reward["common"]}
        elif com < rand <= com + unc:
            return {"type": "uncommon", "value": reward["uncommon"]}
        return {"type": "rare", "value": reward["rare"]}

    @staticmethod
    async def try_feed(user_id, user_sp, item):
        '''
        Checks if item exists and user has enough SP, 
        then sells and feeds the food item to Brie, 
        updating user db with new affection value, 
        and finally returns cost of food to subtract
        '''
        season = StoreHandler.__get_season()
        seasonal_list = {**StoreHandler.store_list["base"], **StoreHandler.store_list[season]}
        whole_list = {k:v for d_k in StoreHandler.store_list for k, v in StoreHandler.store_list[d_k].items()}
        try_food = seasonal_list.get(item, None)
        whole_try = whole_list.get(item, None)
        if try_food is None and whole_try is None:
            raise NoItemError
        elif try_food is None:
            raise OutOfSeasonError
        if user_sp < try_food["cost"]:
            raise NotEnoughSPError
        await db.set_fed_brie_timestamp(user_id)

        affection_to_add = try_food["affection"]
        bond_to_add = try_food.get("bond", None)
        curr_affection = await db.get_value(user_id, "affection")
        if curr_affection + affection_to_add > 100:
            affection_to_add = 100 - curr_affection
        
        if item == "cracker":
            free_feed_used = await db.get_value(user_id, "free_feed")
            if free_feed_used == 1:
                raise FreeFeedUsed
            await db.set_value(user_id, "free_feed", 1)
            await db.add_value(user_id, "affection", affection_to_add)
            return 0
        else:
            await db.add_value(user_id, "bonds_available", 1)
            await db.add_value(user_id, "affection", affection_to_add)
            if bond_to_add is not None:
                await db.add_value(user_id, "bond_level", bond_to_add)
            return try_food["cost"]

    @staticmethod
    async def try_buy(user_id, user_sp, item):
        '''
        Unlocks a permanent item if the user has enough SP
        '''
        perma_items = StoreHandler.store_list["items"]
        try_item = perma_items.get(item, "None")
        if try_item == "None":
            raise NoItemError
        if user_sp < try_item["cost"]:
            raise NotEnoughSPError
        has_item = await db.get_value(user_id, f"has_{item}")
        if has_item == 1:
            raise AlreadyOwnedError
        await db.set_value(user_id, f"has_{item}", 1)
        return try_item["cost"]

    @staticmethod
    async def try_gift(user_id, user_sp, item):
        '''
        Gives Brie a gift and randomly gives the user 
        an amount of affection points. Returns the cost 
        and reward type.
        '''
        gifts = StoreHandler.store_list["gifts"]
        try_gift = gifts.get(item, "None")
        if try_gift == "None":
            raise NoItemError
        if user_sp < try_gift["cost"]:
            raise NotEnoughSPError
        
        reward = StoreHandler.gamble_puzzle(item, 60, 30)
        affection_to_add = reward["value"]
        curr_affection = await db.get_value(user_id, "affection")
        if curr_affection + affection_to_add > 100:
            affection_to_add = 100 - curr_affection
        
        await db.add_value(user_id, "affection", affection_to_add)
        return {"cost": try_gift["cost"], "reward": reward["type"]}
