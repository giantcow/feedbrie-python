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

class DatabaseError(Exception):
    def __init__(self, message="This is a generic database error."):
        self.message = message

class InvalidFieldError(Exception):
    def __init__(self, field, table="users"):
        self.message = f"{field} is not a valid column in the {table} table!"

class NonBooleanType(Exception):
    def __init__(self, message="The passed variable must be of type boolean!"):
        self.message = message

class InvaludUserIdType(Exception):
    def __init__(self, user_id):
        self.message = f"{user_id} is not a valid user id!"

class Database():

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

    __user_fields = __get_table_fields("users")

    async def create_new_user(user_id, username):
        '''
        Creates new user entry with default values from config.
        '''
        try:
            now = time.time()
            now = dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")

            # By not updating last_fed_brie_timestamp it inherits the default value defined by the table schema.
            cursor.execute(
                "INSERT INTO users (username,user_id,affection,bond_level,bonds_available,has_feather,has_brush,has_scratcher,free_feed,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                (username,user_id,0,0,0,0,0,0,1,now,now)
            )
        except mariadb.Error as error:
            log.error("Failed to create new user: %s", error)

    async def get_created_timestamp(user_id):
        '''
        Returns timestamp for when the user entry was created.
        '''
        try:
            cursor.execute("SELECT created_at FROM users WHERE user_id = %s", [user_id])
            res = cursor.fetchall()
            return res[0][0]
        except mariadb.Error as error:
            log.error("Failed to get created_at timestamp for user_id: %s \n %s" % (user_id, error))

    async def get_updated_timestamp(user_id):
        '''
        Returns the last time the given User's entry was updated.
        '''
        try:
            cursor.execute("SELECT updated_at FROM users WHERE user_id = %s", [user_id])
            res = cursor.fetchall()
            return res[0][0]
        except mariadb.Error as error:
            log.error("Failed to get updated_at timestamp for user_id: %s \n %s" % (user_id, error))

    async def set_value(index, val_name, val):
        if val_name not in __user_fields: raise InvalidFieldError(field=val_name)

        try:
            cursor.execute("UPDATE users SET %s = %s WHERE user_id = %s", (val_name, val, index))
        except mariadb.Error as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))
    
    async def add_value(index, val_name, val):
        if val_name not in __user_fields: raise InvalidFieldError(field=val_name)

        try:
            cursor.execute("UPDATE users SET %s = %s + %s WHERE user_id = %s", (val_name, val_name, val, index))
        except mariadb.Error as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))

    async def remove_value(index, val_name, val):
        if val_name not in __user_fields: raise InvalidFieldError(field=val_name)

        try:
            cursor.execute("UPDATE users SET %s = %s - %s WHERE user_id = %s", (val_name, val_name, val, index))
        except mariadb.Error as error:
            log.error("Failed to set %s to %s for user_id: %s \n %s" % (val_name, val, index, error))

    async def get_value(index, val_name):
        if val_name not in __user_fields: raise InvalidFieldError(field=val_name)

        try:
            cursor.execute("SELECT %s FROM users WHERE user_id = %s", (index, val_name))
            res = cursor.fetchall()
            return res[0][0]
        except mariadb.Error as error:
            log.error("Failed to get %s for user_id: %s \n %s" % (val_name, index, error))

    #################
    #   Feeding     #
    #################
    async def set_fed_brie_timestamp(user_id, fed_timestamp=time.time().dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")):
        '''
        Updates the last time a user has fed Brie.
        '''
        set_value(user_id, "last_fed_brie_timestamp", fed_timestamp)

    async def get_last_fed_timestamp(user_id):
        '''
        Returns timestamp of User's last feeding.
        '''
        return get_value(user_id, "last_fed_brie_timestamp")