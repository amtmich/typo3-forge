import streamlit as st
from elasticsearch_module import Elasticsearch
from result_renderer import ElasticsearchResultRenderer
from dotenv import load_dotenv, dotenv_values
import os
load_dotenv()

class StreamlitApp:
    def __init__(self, es_client):
        self.es_client = es_client

    def run(self):
        st.title("TYPO3 forge")

        record_id = st.text_input("Enter issue ID:", value="")

        if st.button("Search"):
            if not record_id.isdigit():
                st.error("Please enter a valid integer ID.")
                return

            record = self.es_client.get_record_by_id(record_id)

            if not record:
                st.error("No record found with the provided ID.")
                return

            main_result = ElasticsearchResultRenderer.render_main_result(record)
            st.success(main_result)

            ##Standard Elasaticsearch
            field_values = {
                "subject": record['_source'].get('subject', '')
            }
            description = record['_source'].get('description', '')
            if description:
                field_values["description"] = description

            similar_results = self.es_client.full_text_search(field_values=field_values, size=os.environ.get('result_count'), exclude_ids=[record_id])

            if not similar_results['hits']['hits']:
                st.info("No similar records found.")
                return

            similar_output = ElasticsearchResultRenderer.render_similar_results(similar_results)
            st.markdown(similar_output)

if __name__ == "__main__":
    elasticsearch_client = Elasticsearch()
    app = StreamlitApp(elasticsearch_client)
    app.run()
