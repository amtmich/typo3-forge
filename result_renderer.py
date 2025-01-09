class ElasticsearchResultRenderer:
    @staticmethod
    def render_main_result(record):
        id = record['_id']
        status = record['_source'].get('status')
        subject = record['_source'].get('subject', 'No Subject')
        return f"https://forge.typo3.org/issues/{id}: {subject} ({status})"

    @staticmethod
    def render_similar_results(results, extra_field = ''):
        output = "Similar issues found:\n\n"
        for idx, hit in enumerate(results['hits']['hits'], start=1):
            id = hit['_id']
            status = hit['_source'].get('status')
            score = hit['_score']
            subject = hit['_source'].get('subject', 'No Subject')
            output += f"{status} #{idx} ({score}): https://forge.typo3.org/issues/{id}: {subject}\n\n"

            if extra_field:
                extra_field_value = hit['_source'].get(extra_field, '')
                output += f"{extra_field_value}\n\n"
        return output
