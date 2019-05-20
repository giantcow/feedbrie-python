import aiohttp
import json

class StreamElementsAPI:
    def __init__(self, channel, aio_session):
        self.channel = channel
        self.aio_session = aio_session

    async def get_user_points(self, user):
        async with self.aio_session.get('https://api.streamelements.com/kappa/v2/points/%s/%s' % (self.channel, user)) as response:
            data = await json.loads(response)
            return data['points']

    # Append to a user's points, value is an INT, negative will decrease points
    async def set_user_points(self, user, value):
        async with self.aio_session.put('https://api.streamelements.com/kappa/v2/points/%s/%s/%d' % (self.channel, user, value)) as response:
            data = await json.loads(response)
            return data['newAmount']