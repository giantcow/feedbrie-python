import logging
import MySQLdb as mariadb
import time
import datetime as dt

log = logging.getLogger("database")
epicfilehandler = logging.FileHandler("database.log")
epicfilehandler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.setLevel(logging.DEBUG)
log.addHandler(epicfilehandler)

mariadb_connection = mariadb.connect(host="localhost", user='brie', password='3th3rn3t', db='Brie', autocommit=True)
cursor = mariadb_connection.cursor()

class DatabaseException(Exception):
    def __init__(self, message="This is a generic database error."):
        self.message = message

class InvalidFieldException(Exception):
    def __init__(self, field, table="users"):
        self.message = f"{field} is not a valid column in the {table} table!"

class NonBooleanTypeException(Exception):
    def __init__(self, message="The passed variable must be of type boolean!"):
        self.message = message

class InvaludUserIdTypeException(Exception):
    def __init__(self, user_id, reason):
        self.message = f"{user_id} is not a valid user id because: {reason}"

class Database():

    @staticmethod
    def user_id_check(user_id):
        if isinstance(user_id, str):
            if len(user_id) > 100:
                raise InvaludUserIdTypeException(user_id=user_id, reason="Max ID length is 100 characters")
        else:
            raise InvaludUserIdTypeException(user_id=user_id, reason="Non-string type.")

    @staticmethod
    def __get_table_fields(table):
        fields = []
        try:
            cursor.execute("SHOW COLUMNS FROM %s", [table])
            res = cursor.fetchall()
            for field in res:
                field.append(field[0])
            return fields
        except mariadb.Error as error:
            log.error("Failed to get table columns: %s", error)

    __user_table_fields = __get_table_fields("users")

    @staticmethod
    async def create_new_user(user_id, username):
        '''
        Creates new user entry with default values from config.
        '''
        try:
            Database.user_id_check(user_id)
            now = time.time()
            now = dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")

            # By not updating last_fed_brie_timestamp it inherits the default value defined by the table schema.
            cursor.execute(
                "INSERT INTO users (username,user_id,affection,bond_level,bonds_available,has_feather,has_brush,has_scratcher,free_feed,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                (username,user_id,0,0,0,0,0,0,1,now,now)
            )
        except (mariadb.Error, InvaludUserIdTypeException) as error:
            log.error("Failed to create new user: %s", error)

    @staticmethod
    async def set_value(index, val_name, val):
        if val_name not in Database.__user_table_fields: raise InvalidFieldException(field=val_name)

        try:
            Database.user_id_check(index)
            cursor.execute("UPDATE users SET %s = %s WHERE user_id = %s", (val_name, val, index))
        except (mariadb.Error, InvaludUserIdTypeException) as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))

    @staticmethod
    async def add_value(index, val_name, val):
        if val_name not in Database.__user_table_fields: raise InvalidFieldException(field=val_name)

        try:
            Database.user_id_check(index)
            cursor.execute("UPDATE users SET %s = %s + %s WHERE user_id = %s", (val_name, val_name, val, index))
        except (mariadb.Error, InvaludUserIdTypeException) as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))

    @staticmethod
    async def remove_value(index, val_name, val):
        if val_name not in Database.__user_table_fields: raise InvalidFieldException(field=val_name)

        try:
            Database.user_id_check(index)
            cursor.execute("UPDATE users SET %s = %s - %s WHERE user_id = %s", (val_name, val_name, val, index))
        except (mariadb.Error, InvaludUserIdTypeException) as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))

    @staticmethod
    async def get_value(index, val_name):
        if val_name not in Database.__user_table_fields: raise InvalidFieldException(field=val_name)

        try:
            Database.user_id_check(index)
            cursor.execute("SELECT %s FROM users WHERE user_id = %s", (val_name, index))
            res = cursor.fetchall()
            return res[0][0]
        except (mariadb.Error, InvaludUserIdTypeException) as error:
            log.error("Failed to get %s for user_id: %s \n %s" % (val_name, index, error))

    #########################
    #                       #
    #       Helpers         #
    #                       #
    #########################

    @staticmethod
    async def get_created_timestamp(user_id):
        '''
        Returns timestamp for when the user entry was created.
        '''
        return await Database.get_value(user_id, "created_at")

    @staticmethod
    async def get_updated_timestamp(user_id):
        '''
        Returns the last time the given User's entry was updated.
        '''
        return await Database.get_value(user_id, "updated_at")

    @staticmethod
    async def set_fed_brie_timestamp(user_id, fed_timestamp=dt.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")):
        '''
        Updates the last time a user has fed Brie.
        '''
        await Database.set_value(user_id, "last_fed_brie_timestamp", fed_timestamp)

    @staticmethod
    async def get_last_fed_timestamp(user_id):
        '''
        Returns timestamp of User's last feeding.
        '''
        return await Database.get_value(user_id, "last_fed_brie_timestamp")