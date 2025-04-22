# buildsql.py
import re
import json
import ast
import logging
from kgq import KnownGoodQueries
import pandas as pd

logging.basicConfig(level=logging.INFO)

class SQLBuilder:
    def __init__(self, bigquery_client, openai_client):
        self.bigquery_client = bigquery_client
        self.client = openai_client
        self.kgq = KnownGoodQueries()
        self.metadata = None


    @staticmethod
    def clean_column_alias(sql):
        """Clean column aliases to be BigQuery compatible."""
        # Replace quoted aliases with underscore-based names
        def replace_alias(match):
            alias = match.group(1)
            # Convert spaces and special characters to underscores
            clean_alias = re.sub(r'[^a-zA-Z0-9]', '_', alias)
            # Ensure it starts with a letter
            if not clean_alias[0].isalpha():
                clean_alias = 'col_' + clean_alias
            return f"AS {clean_alias}"
        
        # Pattern matches AS "Some Name" or as "Some Name"
        sql = re.sub(r'(?i)AS\s*"([^"]+)"', replace_alias, sql)
        return sql

    @staticmethod
    def extract_sql(response_text):
        """Extract SQL code from response and clean column aliases."""
        match = re.search(r'```sql\n(.*?)\n```', response_text, re.DOTALL)
        if match:
            sql = match.group(1).strip()
            # Clean the SQL to make it BigQuery compatible
            sql = SQLBuilder.clean_column_alias(sql)
            return sql
        else:
            raise ValueError("No SQL code found in the response")

    def execute_query(self, query):
        """Execute a BigQuery SQL query with intelligent column renaming."""
        if not query or not isinstance(query, str):
            logging.error("Invalid query provided. Query must be a non-empty string.")
            return None

        try:
            # Execute query and get DataFrame
            df = self.bigquery_client.query(query).to_dataframe()
            
            if df.empty:
                logging.warning("Query returned an empty DataFrame.")
                return None

            # Convert datetime columns to simple date strings
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.tz_localize(None).dt.strftime('%Y-%m-%d')

            # Prepare prompt for column renaming
            column_prompt = f"""
            Here are the original database columns: {list(df.columns)}

            Rename them professionally with the following rules:
            - Proper capitalization
            - Use units where applicable (e.g., minutes, kW, etc.)
            - Convert underscores to spaces
            
            Example Mappings:
            - 'total_disconnection_duration' → 'Total Disconnection Duration (minutes)'
            - 'avg_power_kw' → 'Average Power (kW)'
            - 'battery_backup_hrs' → 'Battery Backup (Hours)'

            Return only a **valid Python dictionary**        
             """


            # Generate column rename mapping using OpenAI
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Respond only with the requested Python dictionary."},
                    {"role": "user", "content": column_prompt}
                ],
                temperature=0
            )
            
            rename_text = response.choices[0].message.content.strip()

            try:
                # Remove code block markers and parse the response
                rename_text = re.sub(r'^```python\n', '', rename_text)
                rename_text = re.sub(r'\n```$', '', rename_text)
                column_rename_map = ast.literal_eval(rename_text)

                if not isinstance(column_rename_map, dict):
                    raise ValueError("Generated rename map is not a dictionary.")

                # Rename columns
                df.rename(columns=column_rename_map, inplace=True)
                logging.info(f"Columns renamed successfully: {column_rename_map}")

            except (SyntaxError, ValueError, TypeError) as parse_error:
                logging.error(f"Error parsing column rename map: {parse_error}")
                logging.warning("Returning DataFrame with original column names.")

            # Eliminate duplicate rows if applicable
            df.drop_duplicates(inplace=True)
            return df

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None

    def generate_sql_prompt(self, user_query, metadata, context=None):
        """Generate an advanced SQL query prompt."""
        # Extract the desired number of rows using AI
        
        metadata_str = json.dumps(metadata, indent=2) if metadata else "No metadata available"

        if context and 'conversation_history' in context:
            context_list = []
            for entry in context['conversation_history']:
                context_list.append({
                    'sql': entry['generated_sql'],
                    'analysis': entry['analysis']
                })
            context_str = json.dumps(context_list, indent=2)
        else:
            context_str = "No previous context"

        prompt = f"""
            ## SQL Query Generation Guidelines:

            ### **1. Query Context:**
            - **User Request:** {user_query}
            - **Metadata (Table & Column Descriptions):** {metadata}
            - **Conversation Context:** {context_str}

            ### **2. Key SQL Generation Rules:**
            - Use **only the provided metadata** for column names. Do not hallucinate any columns.
            - Remember you are writing sql queries for BIGQUERY.
            - Prioritize business-critical columns for clarity.
            - Convert **technical column names** into business-friendly terms where necessary.
            - Ensure queries generate **clear, actionable tables**.
            - If `siteid` is present, it **must be the first column**.
            - Round numeric values to **2 decimal places** where applicable.



            ### **3. Table-Specific Rules:**
            - If the query involves **fuel consumption**, use `edgepointprod.Axin_Data.dailyfueldata`.
            - If consumption is `0.0`, it means no fuel was consumed.
            - Access dates as: `DATE(time) = 'YYYY-MM-DD'` the year will not be earlier than 2024.

            - Use 'edgepointprod.Axin_Data.siteinfra' for details regarding infrastructure of the sites like counts, models, availability status, province, area. 

            - Use `edgepointprod.Axin_Data.site` only for matching companyId with siteId. No other columns are necessary.

            - If the query involves **run hours**, use `edgepointprod.Axin_Data.performancedaily`.
            - Run hours range from **0 to 24 per day**.
            - Never use hourly tables, as they contain fractional values **(0-1 per hour).**

            ### **4. Formatting Rules for MAX/MIN Queries:**
            - Always include **the date column** in the result.
            - If ranking by **highest/lowest values**, sort accordingly and **exclude NULL values**.         
            
            - Example format:
                ```
                SELECT 
                    s.siteid,
                    s.sitename,
                    metric_value,
                    DATE(timestamp_column) AS metric_date
                FROM [table]
                WHERE [conditions]
                ORDER BY metric_value DESC/ASC
                ```

            CRITICAL: The SQL query should ALWAYS:
                - Dynamically use the companyId from the 'edgepointprod.Axin_Data.site' table
                - Join the relevant tables and retrieve data
                - Format dates appropriately using DATE() function
            
            Output a SQL query that addresses the user's intent with clarity and precision.
        """

        return prompt

    def generate_sql_query(self, user_query, metadata, context=None):
        """Generate SQL query using known good queries or OpenAI."""
        
        self.metadata = metadata
        if not self.metadata:
            logging.info("No metadata")
            return None

        # Try to find exact match first
        exact_match = self.kgq.find_exact_match(user_query)
        if exact_match:
            logging.info("✅Test Passed: Found exact matching query")
            return exact_match

        # Try to find similar match
        similar_match = self.kgq.find_similar_match(user_query)
        if similar_match:
            logging.info("✅Test Passed: Found similar matching query")
            return similar_match

        # If no matches found, generate new query
        try:
            prompt = self.generate_sql_prompt(user_query, self.metadata, context)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Generate SQL queries based on user requirements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            # Extract and print the generated response (including the SQL and explanation)
            #generated_response = response.choices[0].message.content.strip()
            #logging.info(f"SQL Query and Explanation:\n{generated_response}")
            query = self.extract_sql(response.choices[0].message.content)
            logging.info("✅ Generated new query using OpenAI")

            return query
        except Exception as e:
            logging.error(f"Error generating SQL query: {e}")
            return None
