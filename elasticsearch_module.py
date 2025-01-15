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
        self.es = ElasticClient(
            f"http://{host}:{port}",
            basic_auth=(username, password)
        )
        self.index_name = index_name
        self.size = os.environ.get('result_count')

        # Create index if it doesn't exist
        if not self.es.indices.exists(index=self.index_name):
            self.es.indices.create(index=self.index_name)

    def get_record_by_id(self, record_id):
        try:
            return self.es.get(index=self.index_name, id=record_id)
        except NotFoundError:
            return None
        
    def search_by_field(self, field, query, size=os.environ.get('result_count')):
        search_body = {
            'query': {
                'match': {
                    field: query,
                }
            },
            'size': size
        }

        return self.es.search(index=self.index_name, body=search_body, explain=True)

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
    
    def more_like_this(self, field_name, record_id):
        mlt_query = {
            "query": {
                "more_like_this": {
                    "fields": [field_name],
                    "like": [{"_index": self.index_name, "_id": record_id}],
                    "min_term_freq": 1,
                    "max_query_terms": 10
                }
            },
            "size": self.size 
        }

        return self.es.search(index=self.index_name, body=mlt_query)
    
    def search_by_terms(self, field_name, terms, exclude_ids=None):
        query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match": {
                                field_name: {
                                    "query": term,
                                    "fuzziness": "AUTO"
                                }
                            }
                        } for term in terms
                    ],
                    "minimum_should_match": 1,
                    "must_not": [
                        {"ids": {"values": exclude_ids}}  # Exclude documents by ID
                    ] if exclude_ids else []
                }
            },
            "size": self.size 
        }
        return self.es.search(index=self.index_name, body=query)
    
    def get_ids_from_search_results(self, search_results):
        """
        Extract IDs from Elasticsearch search results.

        Args:
            search_results (dict): The results returned by the Elasticsearch search function.

        Returns:
            list: A list of unique IDs extracted from the search results.
        """
        hits = search_results.get('hits', {}).get('hits', [])

        ids = [hit['_id'] for hit in hits if '_id' in hit]

        return list(set(ids))
    
    def search_by_embedding(self, field: str, query_vector: list, size: int = 5):
        search_query = {
            "size": size,
            "query": {
                "script_score": {
                    "query": {
                        "match_all": {}
                    },
                    "script": {
                        "source": f"""
                            if (doc['{field}'].size() != 0) {{
                                return cosineSimilarity(params.query_vector, '{field}') + 1.0;
                            }} else {{
                                return 0;  // or use a default score for documents without embeddings
                            }}
                        """,
                        "params": {
                            "query_vector": query_vector
                        }
                    }
                }
            }
        }
        # Execute the search query
        try:
            response = self.es.search(index=self.index_name, body=search_query)
        except Exception as e:
            print(e)

        # Extract and return the results
        return response
