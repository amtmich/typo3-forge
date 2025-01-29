import os
import re
import streamlit as st
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load environment variables from .env (if present)
load_dotenv()

# Helper function to safely convert env strings to bool
def env_to_bool(value, default=False):
    if value is None:
        return default
    return value.lower() in ["true", "1", "yes", "y"]

# Read .env variables
ELASTICSEARCH_HOST = os.getenv("elasticsearch_host", "http://127.0.0.1:9200")
ELASTICSEARCH_USERNAME = os.getenv("elasticsearch_username", "")
ELASTICSEARCH_PASSWORD = os.getenv("elasticsearch_password", "")
INDEX_NAME = os.getenv("index_name", "typo3_with_notes")

RESULT_COUNT = int(os.getenv("result_count", "10"))
FORGE_LINK_BASE = os.getenv("forge_link_base", "http://example.com/")
DEBUG = env_to_bool(os.getenv("debug", "False"))
CONFIGURATION = env_to_bool(os.getenv("configuration", "True"))
STATISTICS = env_to_bool(os.getenv("statistics", "False"))

SEARCH_FIELD = os.getenv("search_field", "relations")  # must be a field that holds list-like data
SEARCH_FIELD_DISPLAY_NAME = os.getenv("search_field_display_name", "Tags (AI generated)")

SEARCH_FIELD_2 = os.getenv("search_field_2", "relations_sequence")
SEARCH_FIELD_2_DISPLAY_NAME = os.getenv("search_field_2_display_name", "Sentences (AI generated)")

# Boost values
DEFAULT_SUBJECT_BOOST = float(os.getenv("subject_boost", "1"))
DEFAULT_SEARCH_FIELD_BOOST = float(os.getenv("search_field_boost", "0.2"))
DEFAULT_SEARCH_FIELD_2_BOOST = float(os.getenv("search_field_2_boost", "0.000001"))

SEARCH_FUNCTION = os.getenv("search_function", "search_similar_records")

# We won't demonstrate multiple_evaluation_... usage here unless needed
# but we read them to avoid possible errors
MULTIPLE_EVAL_COUNT = int(os.getenv("multiple_evaluation_count", "10"))
MULTIPLE_EVAL_SUBJECT_BOOST = os.getenv("multiple_evaluation_subject_boost", "[0.01, 0.1, 0.5]")
MULTIPLE_EVAL_SEARCH_FIELD_BOOST = os.getenv("multiple_evaluation_search_field_boost", "[0.2, 0.5, 1.0, 1.5, 2.0]")
MULTIPLE_EVAL_SEARCH_FIELD_2_BOOST = os.getenv("multiple_evaluation_search_field_2_boost", "[0.2, 0.5, 1.0, 1.5, 2.0]")
MULTIPLE_EVAL_SEARCH_FUNCTION = os.getenv("multiple_evaluation_search_function", '["search_similar_records", "search_similar_records2"]')


class ElasticsearchClient:
    def __init__(self, host, username, password, index_name):
        # Connect to Elasticsearch (no port or scheme passed separately)
        self.client = Elasticsearch(
            hosts=[host],
            http_auth=(username, password)
        )
        self.index_name = index_name

    def count_documents(self):
        """Return total document count in the index."""
        result = self.client.count(index=self.index_name)
        return result["count"]

    def count_field_nonempty(self, field_name):
        """Count number of records that have a non-empty value in field_name."""
        # We can check existence with 'exists'
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": field_name}}
                    ]
                }
            }
        }
        result = self.client.count(index=self.index_name, body=query)
        return result["count"]

    def count_field_in_updated_via(self, field_name):
        """
        Count how many documents have 'updated_via' that matches the string field_name.
        Because updated_via is text, we do a simple match query.
        Adjust if you need exact matches vs partial matches, etc.
        """
        query = {
            "query": {
                "match": {
                    "updated_via": field_name
                }
            }
        }
        result = self.client.count(index=self.index_name, body=query)
        return result["count"]

    def get_document_by_id(self, doc_id):
        """
        Fetch the document by 'id' field (NOT by _id).
        Adjust if you need to search by _id instead.
        """
        # If your 'id' is the _id, you can use get(index, id=doc_id).
        # But if 'id' is a field, we do a search.
        query = {
            "query": {
                "term": {
                    "id.keyword": doc_id
                }
            }
        }
        resp = self.client.search(index=self.index_name, body=query, size=1)
        if resp["hits"]["total"]["value"] > 0:
            return resp["hits"]["hits"][0]["_source"]
        return None

    def search_similar_records(
        self,
        reference_record,
        search_field_list,
        search_field_2_list,
        subject_boost,
        search_field_boost,
        search_field_2_boost,
        exclude_id,
        result_count,
        debug=False
    ):
        """
        Search for similar records using 'should' clauses for:
         - subject
         - items from search_field_list
         - items from search_field_2_list
        Exclude the reference record by 'exclude_id'.
        """

        subject_value = reference_record.get("subject", "")

        should_clauses = []

        # Add subject clause (if not empty)
        if subject_value.strip():
            should_clauses.append({
                "match": {
                    "subject": {
                        "query": subject_value,
                        "boost": subject_boost
                    }
                }
            })

        # Add search_field items
        for item in search_field_list:
            if item.strip():
                should_clauses.append({
                    "match": {
                        SEARCH_FIELD: {
                            "query": item.strip(),
                            "boost": search_field_boost
                        }
                    }
                })

        # Add search_field_2 items
        for item in search_field_2_list:
            if item.strip():
                should_clauses.append({
                    "match": {
                        SEARCH_FIELD_2: {
                            "query": item.strip(),
                            "boost": search_field_2_boost
                        }
                    }
                })

        query_body = {
            "query": {
                "bool": {
                    "must_not": [
                        {"term": {"id.keyword": exclude_id}}
                    ],
                    "should": should_clauses
                    # "minimum_should_match": 1  # if you only want docs that match at least one
                }
            },
            "size": result_count
        }

        # If debug is True, we want to see explanation
        if debug:
            query_body["explain"] = True

        response = self.client.search(index=self.index_name, body=query_body)

        return response, query_body

    def search_similar_records2(
        self,
        reference_record,
        search_field_list,
        search_field_2_list,
        subject_boost,
        search_field_boost,
        search_field_2_boost,
        exclude_id,
        result_count,
        debug=False
    ):
        """
        A second version of search, if you want to compare different query approaches.
        For demonstration, we'll do the same as above or alter slightly.
        """
        # This can differ if you'd like. For example, we might do a multi_match approach, etc.
        # Here we do the same to illustrate how you can switch between search functions.
        return self.search_similar_records(
            reference_record,
            search_field_list,
            search_field_2_list,
            subject_boost,
            search_field_boost,
            search_field_2_boost,
            exclude_id,
            result_count,
            debug=debug
        )


def main():
    st.title("TYPO3 forge issues")

    # Instantiate our client
    es_client = ElasticsearchClient(
        host=ELASTICSEARCH_HOST,
        username=ELASTICSEARCH_USERNAME,
        password=ELASTICSEARCH_PASSWORD,
        index_name=INDEX_NAME
    )

    # SIDEBAR: Show statistics if enabled
    if STATISTICS:
        with st.sidebar.expander("Index Statistics", expanded=True):
            total_docs = es_client.count_documents()
            st.write(f"**Total records**: {total_docs}")

            # For search_field
            a_count_sf = es_client.count_field_nonempty(SEARCH_FIELD)
            b_count_sf = es_client.count_field_in_updated_via(SEARCH_FIELD)
            st.write(
                f"{SEARCH_FIELD_DISPLAY_NAME} ( {SEARCH_FIELD} ): **{a_count_sf} / {b_count_sf}**"
            )

            # For search_field_2
            a_count_sf2 = es_client.count_field_nonempty(SEARCH_FIELD_2)
            b_count_sf2 = es_client.count_field_in_updated_via(SEARCH_FIELD_2)
            st.write(
                f"{SEARCH_FIELD_2_DISPLAY_NAME} ( {SEARCH_FIELD_2} ): **{a_count_sf2} / {b_count_sf2}**"
            )

    # Configuration section in the sidebar (if enabled)
    # We store them in st.session_state so that changes auto trigger re-runs
    if CONFIGURATION:
        st.sidebar.markdown("## Configuration")
        # subject_boost
        if "subject_boost" not in st.session_state:
            st.session_state["subject_boost"] = DEFAULT_SUBJECT_BOOST
        st.session_state["subject_boost"] = st.sidebar.number_input(
            "subject_boost",
            value=st.session_state["subject_boost"],
            step=0.1
        )

        # search_field
        if "search_field" not in st.session_state:
            st.session_state["search_field"] = SEARCH_FIELD
        st.session_state["search_field"] = st.sidebar.text_input(
            "search_field",
            value=st.session_state["search_field"]
        )

        # search_field_boost
        if "search_field_boost" not in st.session_state:
            st.session_state["search_field_boost"] = DEFAULT_SEARCH_FIELD_BOOST
        st.session_state["search_field_boost"] = st.sidebar.number_input(
            "search_field_boost",
            value=st.session_state["search_field_boost"],
            step=0.1
        )

        # search_field_2
        if "search_field_2" not in st.session_state:
            st.session_state["search_field_2"] = SEARCH_FIELD_2
        st.session_state["search_field_2"] = st.sidebar.text_input(
            "search_field_2",
            value=st.session_state["search_field_2"]
        )

        # search_field_2_boost
        if "search_field_2_boost" not in st.session_state:
            st.session_state["search_field_2_boost"] = DEFAULT_SEARCH_FIELD_2_BOOST
        st.session_state["search_field_2_boost"] = st.sidebar.number_input(
            "search_field_2_boost",
            value=st.session_state["search_field_2_boost"],
            step=0.000001,
            format="%.6f"
        )

        # result_count
        if "result_count" not in st.session_state:
            st.session_state["result_count"] = RESULT_COUNT
        st.session_state["result_count"] = st.sidebar.number_input(
            "result_count",
            value=st.session_state["result_count"],
            step=1
        )

        # search_function
        if "search_function" not in st.session_state:
            st.session_state["search_function"] = SEARCH_FUNCTION
        st.session_state["search_function"] = st.sidebar.text_input(
            "search_function",
            value=st.session_state["search_function"]
        )

        # debug
        if "debug" not in st.session_state:
            st.session_state["debug"] = DEBUG
        st.session_state["debug"] = st.sidebar.checkbox(
            "debug",
            value=st.session_state["debug"]
        )

    # If no config, ensure we have fallback local variables
    subject_boost = st.session_state["subject_boost"] if "subject_boost" in st.session_state else DEFAULT_SUBJECT_BOOST
    search_field = st.session_state["search_field"] if "search_field" in st.session_state else SEARCH_FIELD
    search_field_boost = st.session_state["search_field_boost"] if "search_field_boost" in st.session_state else DEFAULT_SEARCH_FIELD_BOOST
    search_field_2 = st.session_state["search_field_2"] if "search_field_2" in st.session_state else SEARCH_FIELD_2
    search_field_2_boost = st.session_state["search_field_2_boost"] if "search_field_2_boost" in st.session_state else DEFAULT_SEARCH_FIELD_2_BOOST
    result_count = st.session_state["result_count"] if "result_count" in st.session_state else RESULT_COUNT
    search_function = st.session_state["search_function"] if "search_function" in st.session_state else SEARCH_FUNCTION
    debug_flag = st.session_state["debug"] if "debug" in st.session_state else DEBUG

    # MAIN: Ask for ID
    st.subheader("Search for Similar Records")
    search_id = st.text_input("Enter an ID (#search_id#):")

    if search_id.strip():
        # 1) Fetch reference record
        reference_record = es_client.get_document_by_id(search_id.strip())
        if not reference_record:
            st.warning(f"No record found with ID={search_id}")
            return

        # Show reference record info
        st.markdown(f"**Subject**: {reference_record.get('subject','')}  \n"
                    f"**ID**: {search_id}  \n"
                    f"**Link**: [{FORGE_LINK_BASE + search_id}]({FORGE_LINK_BASE + search_id})")

        # 2) Gather related IDs
        relations = reference_record.get("relations", "")
        relations_seq = reference_record.get("relations_sequence", "")
        relations_dupe = reference_record.get("relations_dupe", "")

        related_ids = set()
        for rel_str in [relations, relations_seq, relations_dupe]:
            if rel_str:
                # split by whitespace or commas/semicolons
                splitted = re.split(r"[,\s;]+", rel_str.strip())
                # filter out empty strings
                splitted = [x for x in splitted if x.strip()]
                related_ids.update(splitted)

        # We'll show the unique related IDs
        st.markdown(f"**Related IDs from record**: {', '.join(related_ids) if related_ids else 'None'}")

        # 3) The user can pick which items from search_field, search_field_2 to include
        #    We'll read them from the reference record to see what's present
        raw_field_values = reference_record.get(search_field, "")
        raw_field_2_values = reference_record.get(search_field_2, "")

        # Because the specification says these fields might be lists,
        # but your data might be stored as actual Python lists or comma separated strings.
        # We'll do a best-guess approach:
        if isinstance(raw_field_values, list):
            search_field_values_list = [str(x) for x in raw_field_values]
        else:
            # assume string, split
            search_field_values_list = re.split(r"[,\s;]+", raw_field_values.strip()) if raw_field_values else []

        if isinstance(raw_field_2_values, list):
            search_field_2_values_list = [str(x) for x in raw_field_2_values]
        else:
            # assume string, split
            search_field_2_values_list = re.split(r"[,\s;]+", raw_field_2_values.strip()) if raw_field_2_values else []

        st.sidebar.markdown(f"### {SEARCH_FIELD_DISPLAY_NAME} selections")
        selected_search_field_values = []
        for val in search_field_values_list:
            if val.strip():
                # Provide a checkbox
                default_checked = True
                check_val = st.sidebar.checkbox(val, value=default_checked, key=f"sf_{val}")
                # Also an optional input if user wants to adjust the text
                input_val = st.sidebar.text_input(f"Adjust {val}", value=val, key=f"sf_adj_{val}")
                if check_val and input_val.strip():
                    selected_search_field_values.append(input_val.strip())

        st.sidebar.markdown(f"### {SEARCH_FIELD_2_DISPLAY_NAME} selections")
        selected_search_field_2_values = []
        for val in search_field_2_values_list:
            if val.strip():
                default_checked = True
                check_val_2 = st.sidebar.checkbox(val, value=default_checked, key=f"sf2_{val}")
                input_val_2 = st.sidebar.text_input(f"Adjust {val}", value=val, key=f"sf2_adj_{val}")
                if check_val_2 and input_val_2.strip():
                    selected_search_field_2_values.append(input_val_2.strip())

        # 4) Perform the configured search function
        if hasattr(es_client, search_function):
            fn = getattr(es_client, search_function)
        else:
            st.error(f"Search function '{search_function}' not found. Using default 'search_similar_records'.")
            fn = es_client.search_similar_records

        response, used_query = fn(
            reference_record=reference_record,
            search_field_list=selected_search_field_values,
            search_field_2_list=selected_search_field_2_values,
            subject_boost=subject_boost,
            search_field_boost=search_field_boost,
            search_field_2_boost=search_field_2_boost,
            exclude_id=search_id.strip(),
            result_count=result_count,
            debug=debug_flag
        )

        # 5) Print query (if debug)
        if debug_flag:
            st.markdown("#### Debug: Query")
            st.json(used_query)

        hits = response["hits"]["hits"]
        # Count how many of these hits have an id in the related_ids set
        related_count_in_results = 0
        for hit in hits:
            h_id = hit["_source"].get("id", "")
            if h_id in related_ids or str(h_id) in related_ids:
                related_count_in_results += 1

        # 6) Show the progress (count of related records / total count of related ids)
        total_count_of_related_ids = len(related_ids)
        # cast to int (some might already be int, but we ensure we respect requirement)
        st.markdown("**Related IDs count in results**:")
        if total_count_of_related_ids > 0:
            fraction = related_count_in_results / total_count_of_related_ids
        else:
            fraction = 0
        st.progress(fraction)

        # 7) Display the results
        st.subheader("Results")
        for i, hit in enumerate(hits, start=1):
            record_id = hit["_source"].get("id", "")
            record_subject = hit["_source"].get("subject", "")
            record_score = hit["_score"]
            sf_val = hit["_source"].get(search_field, "")
            sf2_val = hit["_source"].get(search_field_2, "")
            url_link = f"{FORGE_LINK_BASE}{record_id}"

            # Check if record_id is in related_ids
            if record_id in related_ids or str(record_id) in related_ids:
                st.markdown(
                    f"### **{i}) ID**: {record_id}, Score={record_score}\n"
                    f"**Subject**: {record_subject}\n"
                    f"[Link]({url_link})\n"
                    f"**{SEARCH_FIELD_DISPLAY_NAME}**: {sf_val}\n"
                    f"**{SEARCH_FIELD_2_DISPLAY_NAME}**: {sf2_val}"
                )
            else:
                # Normal smaller text
                st.markdown(
                    f"**{i}) ID**: {record_id}, Score={record_score}\n\n"
                    f"Subject: {record_subject}\n\n"
                    f"[Link]({url_link})\n\n"
                    f"{SEARCH_FIELD_DISPLAY_NAME}: {sf_val}\n\n"
                    f"{SEARCH_FIELD_2_DISPLAY_NAME}: {sf2_val}"
                )

            # If debug is true, show explanation
            if debug_flag:
                if "_explanation" in hit:
                    with st.expander(f"Explanation for {record_id}"):
                        st.json(hit["_explanation"])

if __name__ == "__main__":
    main()
