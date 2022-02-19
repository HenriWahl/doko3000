# access to CouchDB

from cloudant import CouchDB
from cloudant.document import Document
from cloudant.query import Query


class DB:
    """
    database connection and queries
    """
    def __init__(self, app):
        self.couch = CouchDB(app.config['COUCHDB_USER'],
                             app.config['COUCHDB_PASSWORD'],
                             url=app.config['COUCHDB_URL'],
                             connect=True,
                             auto_renew=True)
        # if not existing create needed databases
        if app.config['COUCHDB_DATABASE'] not in self.couch.all_dbs():
            self.database = self.couch.create_database(app.config['COUCHDB_DATABASE'])
        else:
            self.database = self.couch[app.config['COUCHDB_DATABASE']]

        # workaround to avoid error message about missing '_users' database
        if '_users' not in self.couch:
            self.couch.create_database('_users')

    def add(self, data):
        self.database.create_document(data.__dict__)

    def filter_by_type_as_number(self, filter_type):
        """
        retrieves documents filtered by type and ordered by non-document-id as number for tricks and rounds
        """
        result = {}
        for item in Query(self.database, selector={'type': filter_type}).result:
            item_id = item['_id'].split(f'{filter_type}-', 1)[1]
            result[item_id] = item
        return result

    def filter_by_type_real_id(self, filter_type):
        """
        retrieves documents filtered by type and ordered by document-id, needed for tables and players
        """
        result = {}
        for item in Query(self.database, selector={'type': filter_type}).result:
            result[item['_id']] = item
        return result


class Document3000(Document):
    """
    extend Document class with a conflict-aware save()
    """
    def __init__(self, database=None, document_id=None):
        super().__init__(database=database, document_id=document_id)

    def save(self):
        """
        save() inside try/except for debugging
        """
        try:
            super().save()
        except Exception as error:
            # sleep a random amount of time before next attempt
            print('ERROR', self.document_url)
            print(error)
