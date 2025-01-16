import streamlit as st
from elasticsearch_module import Elasticsearch
from result_renderer import ElasticsearchResultRenderer
from dotenv import load_dotenv, dotenv_values
import os
load_dotenv()

class StreamlitApp:
    def __init__(self):
        self.es_client =  Elasticsearch()
        self.tags_field_name = os.environ.get('search_field')

    def search_provided(self):
        st.session_state["search_clicked"] = True

    def run(self):
        st.title("TYPO3 forge")
        
        if "record" not in st.session_state:
            st.session_state["record"] = None
        if "record_id" not in st.session_state:
            st.session_state["record_id"] = None
        if "search_clicked" not in st.session_state:
            st.session_state["search_clicked"] = False

        st.session_state["record_id"] = st.text_input(
            "Enter issue ID:",
            value=st.session_state["record_id"],
            disabled=st.session_state.search_clicked,
            on_change=self.search_provided
            )

        if st.session_state["record_id"]:
            st.session_state["record"] = self.es_client.get_record_by_id(st.session_state["record_id"])
        else:
            if st.button("Search", on_click=self.search_provided, disabled=st.session_state.search_clicked):
                st.session_state["record"] = self.es_client.get_record_by_id(st.session_state["record_id"])
            
        if st.session_state["record"]:
            self.render_input_with_checkbox(st.session_state["record"]['_source'].get(self.tags_field_name, ''))
            #st.text(self.filter_checked_items())
            self.render_results()

    def render_input_with_checkbox(self, items, force = False):
        # Initialize session state if not already done
        if "item_states" not in st.session_state or force == True:
            st.session_state["item_states"] = {
                index: {"label": item.strip(), "checked": True} for index, item in enumerate(items)
            }

        st.sidebar.title(f"Tags for issue {st.session_state['record_id']} (AI generated)")
        if st.session_state["item_states"]:
            st.sidebar.markdown("- You might adjust tags (adjust text and click enter) - just for test purpose (it won't persist new values in db)")
            st.sidebar.markdown("- If tag is not relevant in your opinion - just uncheck it by clicking 'applied'")        

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
        else:
            st.sidebar.markdown("No tags generated for this issue")

    def filter_checked_items(self):
        return [item['label'] for item in st.session_state["item_states"].values() if item['checked']]
    
    def get_related_ids(self, record):
        # Extract the comma-separated strings from the record
        relations = record.get('relations', None)
        relations_dupe = record.get('relations_dupe', None)
        relations_sequence = record.get('relations_sequence', None)

        # Combine all values into a single string, filtering out None
        all_ids = filter(None, [relations, relations_dupe, relations_sequence])

        # Split the strings into individual IDs and flatten the resulting list
        ids = []
        for id_str in all_ids:
            ids.extend(id_str.split(","))

        # Return a list of unique values
        return list(set(ids))
    
    def get_common_ids(self, record, search_results):
        """
        Get common IDs between unique IDs from the record and IDs from Elasticsearch search results.

        Args:
            record (dict): A dictionary containing the keys 'relations', 'relations_dupe', and 'relations_sequence'.
            search_results (dict): The results returned by the Elasticsearch search function.

        Returns:
            list: A list of IDs common to both sources.
        """
        unique_ids = self.get_related_ids(record)
        search_ids = self.es_client.get_ids_from_search_results(search_results)

        common_ids = list(set(unique_ids).intersection(search_ids))

        return common_ids

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
            #if st.session_state["item_states"]:
            tags = self.filter_checked_items()
        
            similar_results = self.es_client.search_by_terms(
                self.tags_field_name,
                tags,
                st.session_state['record']['_source'],
                [st.session_state["record_id"]]
            )

            st.text(f"Tags of searched issue: {tags}")
            related_ids = self.get_related_ids(st.session_state['record']['_source'])
            common_ids = []
            if related_ids:
                st.text(f"Related issues ids {related_ids}")
                common_ids = self.get_common_ids(st.session_state['record']['_source'], similar_results)
                st.progress(len(common_ids)/len(related_ids), text=f"{len(common_ids)}/{len(related_ids)} related issues found in results.\n{common_ids}")
            similar_output = ElasticsearchResultRenderer.render_similar_results(similar_results, self.tags_field_name, common_ids)
            st.markdown("#### Results")
            st.markdown(similar_output)
            

if __name__ == "__main__":
    app = StreamlitApp()
    app.run()
