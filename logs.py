# logs.py
from google.cloud import bigquery
from datetime import datetime

class QueryLogger:
    def __init__(self, bigquery_client):
        self.client = bigquery_client
        self.table_id = 'edgepointprod.Axin_Data.executionlogs'  
        
    def log_query(self, session_id, user_query, generated_sql=None, analysis=None, feedback=None):
        """Log a query and its details to BigQuery."""
        row = {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'timestamp': datetime.now().isoformat(),
            'user_query': user_query,
            'generated_sql': generated_sql,
            'analysis': analysis,
          #  'feedback': feedback
        }
        
        errors = self.client.insert_rows_json(self.table_id, [row])
        if errors:
            raise Exception(f"Error inserting log: {errors}")
    
    def get_context_history(self, session_id, limit=5):
        """Retrieve recent conversation history for context."""
        query = f"""
        SELECT user_query, generated_sql, analysis
        FROM `{self.table_id}`
        WHERE session_id = @session_id
        ORDER BY timestamp DESC
        LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                bigquery.ScalarQueryParameter("limit", "INTEGER", limit)
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]