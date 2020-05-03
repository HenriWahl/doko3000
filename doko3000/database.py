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

    def filter_by_type(self, filter_type):
        """
        retrieves documents filtered by type and ordered by non-document-id
        """
        result = {}
        for i in Query(self.database, selector={'type': filter_type}).result:
            print(i)
        for item in Query(self.database, selector={'type': filter_type}).result:
            item_id = item['_id'].split(f'{filter_type}-', 1)[1]
            result[item_id] = item
        return result


    def player_documents_by_player_id(self):
        """
        retrieves player documents sorted by non-document-id
        """
        # result = {}
        # for player in Query(self.database, selector={'type': 'player'}).result:
        #     player_id = player['_id'].split('player-', 1)[1]
        #     result[player_id] = player
        # return result
        return self.filter_by_type('player')

    def table_documents_by_table_id(self):
        """
        retrieves table documents sorted by non-document-id
        """
        # result = {}
        # for player in Query(self.database, selector={'type': 'table'}).result:
        #     player_id = player['_id'].split('player-', 1)[1]
        #     result[player_id] = player
        # return result
        return self.filter_by_type('table')
