import logging
import random
import json

log = logging.getLogger("bonds")
epicfilehandler = logging.FileHandler("bonds.log")
epicfilehandler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.setLevel(logging.DEBUG)
log.addHandler(epicfilehandler)

class Bond:
    def __init__(self, name, worth, item, gate, scalemin, scalemax):
        self.name = name
        self.worth = worth
        self.item = item
        self.gate = gate
        self.min = scalemin
        self.max = scalemax

class BondLoader:

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

    def reload_bonds(path="bonds.json"):
        '''
        Reload bonds from disk
        '''
        BondHandler.bond_list = BondLoader.load_bonds(path)
        log.info("Reloading bonds from JSON.")

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

    def try_bond(user_aff, bond):
        '''
        Get and output the value of a bond after attempting it, given a user's affection and a particular bond dict.
        Return the worth.
        Returns 0 if the bond fails.
        '''
        worth = bond["worth"]
        gate = bond["gate_aff"]
        scale_min = bond["scale_min"]
        scale_max = bond["scale_max"]
        success = BondHandler.calculate_success(gate, user_aff, scale_min, scale_max)
        if success:
            return worth
        else:
            return 0
