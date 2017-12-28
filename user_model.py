# coding=utf-8
"""
User Model. Users Mongo Database Interface
"""

import pymongo
import unittest

from magen_utils_apis.datetime_api import SimpleUtc
from magen_mongo_apis.mongo_return import MongoReturn

import db
from config import TEST_DB_NAME, USER_COLLECTION_NAME, EXISTING_EMAIL_CODE_ERR


def _cursor_helper(cursor):
    """ Returns processed list"""
    result = list()
    for cur in cursor:
        if cur.get("creation_timestamp"):
            cur["creation_timestamp"] = cur["creation_timestamp"].replace(
                tzinfo=SimpleUtc()).isoformat()
        result.append(cur)
    return result


class UserModel(object):
    """
    User Model represents a User Entity
    """
    created_index = False

    def __init__(self, db_ctx, email, password, is_authenticated=False, **kwargs):
        """
        User Model constructor

        :param db_ctx: Database context
        :type db_ctx: PyMongo.MongoClient.Database
        :param email: Primary Key for user, email
        :type email: str
        :param password: User's secret hash
        :type password: str
        :param is_authenticated: Authentication flag
        :type is_authenticated: bool
        :param kwargs: user's details

        .. notes:: kwargs may contain:
        - first_name
        - second_name
        - role
        - ...
        """
        self.db_ctx = db_ctx
        self.email = email
        self.password = password
        self.is_authenticated = is_authenticated
        self.is_anonymous = False
        self.is_active = True
        self.details = kwargs

    # def is_active(self):
    #     """True, as all users are active for now."""
    #     return True
    #
    def get_id(self):
        """ Return the email address to satisfy Flask-Login's requirements. """
        return self.email
    #
    # def is_authenticated(self):
    #     """Return True if the user is authenticated."""
    #     return self.authenticated
    #
    # def is_anonymous(self):
    #     """False, as anonymous users aren't supported."""
    #     return False

    def _to_dict(self):
        """
        Convert properties to dictionary

        :return: flat dictionary with properties
        :rtype: dict
        """
        attributes = vars(self)
        attributes.pop('db_ctx')
        for detail in attributes['details']:
            attributes[detail] = attributes['details'][detail]
        del attributes['details']
        return attributes

    def submit(self):
        """
        Submit data into Database.
        Uses db.connect Context Manager.
        Implementation is specific to PyMongo package

        :return: Return Object
        :rtype: Object
        """
        # TODO (Lohita): submit method should be able to do both insert and update
        # TODO: look at magen-core.magen_mongo.magen_mongo_apis.concrete_dao.py
        # TODO: and join current implementation of submit with update_one() from concrete_dao.py
        user_collection = self.db_ctx.get_collection(USER_COLLECTION_NAME)
        if not type(self).created_index:
            user_collection.create_index('email', unique=True)
        return_obj = MongoReturn()
        try:
            result = user_collection.insert_one(self._to_dict())
            if result.acknowledged and result.inserted_id:
                return_obj.success = True
                return_obj.count = 1
                return_obj.message = 'Document inserted successfully'
            else:
                return_obj.success = False
                return_obj.message = "Failed to insert document"
            return return_obj
        except pymongo.errors.PyMongoError as error:
            return_obj.success = False
            return_obj.code = error.code
            return_obj.message = error.details
            return_obj.db_exception = error
            return return_obj

    @classmethod
    def select_by_email(cls, db_instance, email):
        """
        Select a User by email

        :param db_instance:

        :param email: user's e-mail
        :type email: str

        :return: found users or empty list
        :rtype: list
        """
        user_collection = db_instance.get_collection(USER_COLLECTION_NAME)

        seed = dict(email=email)
        projection = dict(_id=False)

        mongo_return = MongoReturn()
        try:
            cursor = user_collection.find(seed, projection)
            result = _cursor_helper(cursor)
            assert len(result) == 1 or len(result) == 0
            mongo_return.success = True
            if len(result):
                mongo_return.documents = cls(db_instance, **result[0])  # email is unique index
                mongo_return.documents.is_authenticated = True
            mongo_return.count = len(result)
            return mongo_return
        except pymongo.errors.PyMongoError as error:
            mongo_return.success = False
            mongo_return.documents = error.details
            mongo_return.code = error.code
            return mongo_return


class TestUserDB(unittest.TestCase):
    """
    Test for Users DB
    """

    def tearDown(self):
        with db.connect(TEST_DB_NAME) as db_instance:
            db_instance.drop_collection(USER_COLLECTION_NAME)

    def test_insert(self):
        """
        Insert User into Mongo DB Test
        """
        test_email = 'test@test.com'
        test_password = 'test_password'
        user_details = dict(
            first_name='Joe',
            last_name='Dow'
        )

        # Insert new document
        with db.connect(TEST_DB_NAME) as db_instance:
            user_obj = UserModel(db_instance, test_email, test_password, **user_details)
            result_obj = user_obj.submit()

        self.assertTrue(result_obj.success)
        self.assertEqual(result_obj.count, 1)

        # Insert same document
        with db.connect(TEST_DB_NAME) as db_instance:
            user_obj = UserModel(db_instance, test_email, test_password, **user_details)
            result_obj = user_obj.submit()

        self.assertFalse(result_obj.success)
        self.assertEqual(result_obj.count, 0)
        self.assertEqual(result_obj.code, EXISTING_EMAIL_CODE_ERR)  # duplicate exception code

    def test_select_by_email(self):
        """
        Select user by email (unique value)
        """
        test_email = 'test@test.com'
        test_password = 'test_password'
        user_details = dict(
            first_name='Joe',
            last_name='Dow'
        )

        # Select non-existing document
        with db.connect(TEST_DB_NAME) as db_instance:
            result_obj = UserModel.select_by_email(db_instance, test_email)
        self.assertTrue(result_obj.success)
        self.assertEqual(result_obj.count, 0)

        # Insert new document
        with db.connect(TEST_DB_NAME) as db_instance:
            user_obj = UserModel(db_instance, test_email, test_password, **user_details)
            result_obj = user_obj.submit()

        self.assertTrue(result_obj.success)
        self.assertEqual(result_obj.count, 1)

        # Select existing document
        with db.connect(TEST_DB_NAME) as db_instance:
            result_obj = UserModel.select_by_email(db_instance, test_email)
        self.assertTrue(result_obj.success)
        self.assertEqual(result_obj.count, 1)
        user_obj = result_obj.documents
        self.assertEqual(user_obj.email, test_email)