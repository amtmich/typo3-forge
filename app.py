import streamlit as st
from elasticsearch_module import Elasticsearch
from result_renderer import ElasticsearchResultRenderer
from Classes.Embeddings.EmbeddingGenerator import EmbeddingGenerator
from dotenv import load_dotenv, dotenv_values
import os
load_dotenv()

class StreamlitApp:
    def __init__(self):
        self.es_client =  Elasticsearch()
        self.tags_field_name = 'FieldsConcatenateUpdater__subject-description__PromptUpdater_test_gemini4'

    def run(self):
        st.title("TYPO3 forge")

        st.session_state["record_id"] = st.text_input("Enter issue ID:", value="")

        if "record" not in st.session_state:
            st.session_state["record"] = None
        if "record_id" not in st.session_state:
            st.session_state["record_id"] = None

        if st.session_state["record_id"]:
            st.session_state["record"] = self.es_client.get_record_by_id(st.session_state["record_id"])
        else:
            if st.button("Search"):
                st.session_state["record"] = self.es_client.get_record_by_id(st.session_state["record_id"])

        #st.text(st.session_state)

        if st.session_state["record"]:
            self.render_input_with_checkbox(st.session_state["record"]['_source'].get(self.tags_field_name, ''))
            #st.text(self.filter_checked_items())
            self.render_results()

    def render_input_with_checkbox(self, items, force = False):
        st.sidebar.title(f"Tags for issue {st.session_state['record_id']} (AI generated)")
        st.sidebar.markdown("- You might adjust tags (adjust text and click enter) - just for test purpose (it won't persist new values in db)")
        st.sidebar.markdown("- If tag is not relevant in your opinion - just uncheck it by clicking 'applied'")
        
        # Initialize session state if not already done
        if "item_states" not in st.session_state or force == True:
            st.session_state["item_states"] = {
                index: {"label": item.strip(), "checked": True} for index, item in enumerate(items)
            }

        # Iterate through the list and render an input field with a checkbox for each item
        for index, item in enumerate(items):
            cols = st.sidebar.columns([4, 1])  # Allocate space for the input field and checkbox

            # Input field for the item text
            with cols[0]:
                new_label = st.sidebar.text_input(f"Tag {index + 1}", value=st.session_state["item_states"][index]["label"])
                st.session_state["item_states"][index]["label"] = new_label

            # Checkbox for the item
            with cols[1]:
                checked = st.sidebar.checkbox("Applied", key=f"checkbox_{index}", value=st.session_state["item_states"][index]["checked"])
                st.session_state["item_states"][index]["checked"] = checked

    def filter_checked_items(self):
        return [item['label'] for item in st.session_state["item_states"].values() if item['checked']]

    def render_results(self):
            main_result = ElasticsearchResultRenderer.render_main_result(st.session_state["record"])
            st.success(main_result)

            ##Standard Elasaticsearch
            # field_values = {
            #     "subject": st.session_state["record"]['_source'].get('subject', '')
            # }
            
            # description = st.session_state["record"]['_source'].get('description', '')
            # if description:
            #     field_values["description"] = description
            
            # all_notes = st.session_state["record"]['_source'].get('all_notes', '')
            # if all_notes:
            #     field_values["all_notes"] = all_notes

            # similar_results = self.es_client.full_text_search(field_values=field_values, size=os.environ.get('result_count'), exclude_ids=[st.session_state["record_id"]])

            # if not similar_results['hits']['hits']:
            #     st.info("No similar records found.")
            #     return

            # similar_output = ElasticsearchResultRenderer.render_similar_results(similar_results)
            # st.markdown(similar_output)

            
            ##Search by given fields
            if st.session_state["item_states"]:
                tags = self.filter_checked_items()
                #st.header(self.tags_field_name)
                st.text(tags)
            
                similar_results = self.es_client.search_by_terms(
                    self.tags_field_name,
                    tags,
                    [st.session_state["record_id"]]
                )
                similar_output = ElasticsearchResultRenderer.render_similar_results(similar_results, self.tags_field_name)
                st.markdown(similar_output)
            

if __name__ == "__main__":
    app = StreamlitApp()
    app.run()
