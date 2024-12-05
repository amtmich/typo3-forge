import os
from elasticsearch import Elasticsearch as ElasticClient
from elasticsearch.exceptions import NotFoundError
from dotenv import load_dotenv, dotenv_values
load_dotenv()

class Elasticsearch:
    def __init__(self, index_name=os.environ.get('index_name'), host=os.environ.get('elasticsearch_host', 'localhost'),
                 port=os.environ.get('elasticsearch_port', '9200'),
                 username=os.environ.get('elasticsearch_username', ''),
                 password=os.environ.get('elasticsearch_password', '')):
        print(123)
        print(password)
        self.es = ElasticClient(
            f"http://{host}:{port}",
            basic_auth=(username, password)
        )
        self.index_name = index_name

        # Create index if it doesn't exist
        if not self.es.indices.exists(index=self.index_name):
            self.es.indices.create(index=self.index_name)

    def get_record_by_id(self, record_id):
        try:
            return self.es.get(index=self.index_name, id=record_id)
        except NotFoundError:
            return None

    def full_text_search(self, field_values, size=5, exclude_ids=None):
        """
        Perform a full-text search with specific values for each field and exclude specific document IDs.

        Args:
            field_values (dict): Dictionary where keys are field names and values are the corresponding search values.
            size (int): Number of results to return (default: 5).
            exclude_ids (list): List of document IDs to exclude (default: None).

        Returns:
            dict: Search results from Elasticsearch.
        """
        must_clauses = [{"match": {field: value}} for field, value in field_values.items()]
        
        body = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "must_not": [
                        {"ids": {"values": exclude_ids}}  # Exclude documents by ID
                    ] if exclude_ids else []
                }
            }
        }
        return self.es.search(index=self.index_name, body=body, size=size)

