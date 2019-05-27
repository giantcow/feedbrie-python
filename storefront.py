import json

class StoreFront:
    def __init__(self):
        with open('store.json') as inv_file:
            self.store = json.load(inv_file)
    
    