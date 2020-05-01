# access to CouchDB

from cloudant import CouchDB
from cloudant.query import Query

class DB:
    """
    database connection and queries
    """
    def __init__(self, app):
        self.couch = CouchDB(app.config['COUCHDB_USER'],
                             app.config['COUCHDB_PASSWORD'],
                             url= app.config['COUCHDB_URL'],
                             connect=True,
                             auto_renew=True)
        # if not existing create needed databases
        if app.config['COUCHDB_DATABASE'] not in self.couch.all_dbs():
            self.database = self.couch.create_database(app.config['COUCHDB_DATABASE'])
        else:
            print(self.couch.all_dbs())
            self.database = self.couch[app.config['COUCHDB_DATABASE']]

    def add(self, data):
        print(data.__dict__)
        print(type(data))
        self.database.create_document(data.__dict__)

    @property
    def players(self):
        """
        only shows player documents - might be filterable more one day
        """
        result = Query(self.database, selector={'type': 'player'}).result
        print(result)
        return Query(self.database, selector={'type': 'player'}).result
