class ElasticsearchResultRenderer:
    @staticmethod
    def render_main_result(record):
        id = record['_id']
        status = record['_source'].get('status')
        subject = record['_source'].get('subject', 'No Subject')
        return f"https://forge.typo3.org/issues/{id}: {subject} ({status})"

    @staticmethod
    def render_similar_results(results, extra_field='', highlight_ids=[]):
        output = ""
        for idx, hit in enumerate(results['hits']['hits'], start=1):
            id = hit['_id']
            status = hit['_source'].get('status', 'Unknown')
            score = hit['_score']
            subject = hit['_source'].get('subject', 'No Subject')
            
            # Check if the current ID is in highlight_ids
            if id in highlight_ids:
                output += f"> ##### {status} #{idx} ({score}): https://forge.typo3.org/issues/{id}: {subject}\n\n"
            else:
                output += f"{status} #{idx} ({score}): https://forge.typo3.org/issues/{id}: {subject}\n\n"

            # Add the extra field if specified
            if extra_field:
                extra_field_value = hit['_source'].get(extra_field, '')
                output += f"{extra_field_value}\n\n"
        
        return output
