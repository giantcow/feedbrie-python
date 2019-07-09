import logging
import random
import json
from db import Database as db

log = logging.getLogger("chatbot")

class NoMoreAttemptsError(Exception):
    def __init__(self):
        self.message = "Out of Bond attempts."

class MissingItemError(Exception):
    def __init__(self, item):
        self.message = f"Missing item: {item}"

class BondFailedError(Exception):
    def __init__(self):
        self.message = "Bond failed."

class BondLoader:

    @staticmethod
    def load_bonds(path="bonds.json"):
        '''
        Load bonds from a JSON file
        '''
        data = {}
        try:
            with open(path) as f:
                data = json.load(f)
        except:
            log.exception("Failed to load Bonds JSON.")
        return data

class BondHandler:

    bond_list = BondLoader.load_bonds()

    @staticmethod
    def reload_bonds(path="bonds.json"):
        '''
        Reload bonds from disk
        '''
        BondHandler.bond_list = BondLoader.load_bonds(path)
        log.info("Reloading bonds from JSON.")

    @staticmethod
    def calculate_success(gate_affection, given_affection, scale_min, scale_max):
        '''
        Calculate a success chance for an event.
        gate_affection is the level of affection the function maxes out at.
        given_affection is the current level of affection.
        scale_max and scale_min are the percentage range for the scaling.
        scale_min is typically 1.
        returns whether or not it passed, by random chance
        '''
        percentage = min(1, (given_affection / gate_affection)) * (scale_max - scale_min) + scale_min
        randomval = random.randint(1, 100)
        return percentage >= randomval

    @staticmethod
    async def handle_item(user_id, bond):
        '''
        Check the required item for the given ID and bond
        Return true or false depending on success
        '''
        if bond["item"] == "":
            return True
        item = bond["item"].lower()
        table_entry = f"has_{item}"
        has_item = await db.get_value(user_id, table_entry)
        return has_item >= 1

    @staticmethod
    async def try_bond(user_id, bond):
        '''
        Get and output the value of a bond after attempting it, given a user's affection and a particular bond dict.
        Return True if it passes and modifies the bond level respectively.
        Raises some exception which describes the problem with the bond attempt otherwise.
        '''
        can_try = await db.get_value(user_id, "bonds_available")
        if can_try <= 0:
            raise NoMoreAttemptsError

        has_item = await BondHandler.handle_item(user_id, bond)
        if not has_item:
            raise MissingItemError(bond["item"])
        
        await db.remove_value(user_id, "bonds_available", 1)
        user_aff = await db.get_value(user_id, "affection")
        success = False
        if bond.get("min_aff", None) is None or user_aff >= bond["min_aff"]:
            worth = bond["worth"]
            gate = bond["gate_aff"]
            scale_min = bond["scale_min"]
            scale_max = bond["scale_max"]
            success = BondHandler.calculate_success(gate, user_aff, scale_min, scale_max)
        if success:
            await db.add_value(user_id, "bond_level", worth)
        else:
            raise BondFailedError
