import aiohttp

# import json

class StreamElementsAPI:
    def __init__(self, channel, jwt_id, loop):
        self.channel = channel
        self.JWT_ID = jwt_id
        self.aio_session = None
        self.loop = loop

        # needs to be done to get the aio_session correctly
        self.loop.create_task(self.set_aio(jwt_id))

    async def set_aio(self, jwt_id):
        self.aio_session = aiohttp.ClientSession(headers={"Authorization": "Bearer %s" % jwt_id})

    async def get_user_points(self, user):
        async with self.aio_session.get('https://api.streamelements.com/kappa/v2/points/%s/%s' % (self.channel, user)) as response:
            data = await response.json()
            return data['points']

    # Append to a user's points, value is an INT, negative will decrease points
    async def set_user_points(self, user, value):
        async with self.aio_session.put('https://api.streamelements.com/kappa/v2/points/%s/%s/%d' % (self.channel, user, value)) as response:
            data = await response.json()
            return data['newAmount']