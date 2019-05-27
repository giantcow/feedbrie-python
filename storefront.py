import json
import logging
import random
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
    def __init__(self, item):
        self.message = f"{item} is not a store item."

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
    def reload_store(path="store.json"):
        '''
        Reload store from disk
        '''
        StoreHandler.store_list = StoreLoader.load_store(path)
        log.info("Reloading store from JSON.")