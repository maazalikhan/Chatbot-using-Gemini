# analysis.py
import json
import pandas as pd

class DataAnalyzer:
    def __init__(self, openai_client):
        self.client = openai_client


    def analyze_data(self, df, user_query, results_df):
        """Analyze the DataFrame using OpenAI."""

        # Handle empty or None results
        if df is None or df.empty:
            empty_result_prompt = f"""
                Analyze this query that returned no results: "{user_query}"
                
                Response Guidelines:
                - Start with a clear statement about what was found (or not found)
                - If no data exists, state this as a neutral fact
                - Be specific about what the query was looking for
                - Keep the tone professional and factual
                - Format in markdown if using emphasis
                - Avoid company identifiers
                - Keep response under 20 words
                - Avoid phrases like "it looks like" or "it seems"
            """
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a data analyst providing clear, concise responses about query results."},
                        {"role": "user", "content": empty_result_prompt}
                    ],
                    temperature=0
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                return "No matching data was found for your query. Please try adjusting your search criteria."
        
        # Prepare data context for non-empty results
        data_summary = {
            'total_rows': len(df),
            'columns': list(df.columns)
        }
        
        # Format datetime columns
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str).str[:10]

        data_str = df.head(5).to_string(index=False)
        
        prompt = f"""
            Analyze the following data and create a clear, structured report.
            
            User Query: {user_query}
            Query Results: {results_df}

            Data Overview
            - Total Rows: {data_summary['total_rows']}
            - Columns: {', '.join(data_summary['columns'])} 
            - Sample Data: {data_str}

            Prompt:

            Goal:
            Analyze the given data concisely with:

            A brief summary of key metrics (e.g., total count, distribution across areas and provinces).
            Recognize any patterns or trends (e.g., clustering of sites, high-density areas, or unusual distributions).
            Identify relationships between the data points (e.g., areas with higher site counts may suggest higher demand, or certain provinces showing rapid growth).
            Return Format:

            Use bullet points, or sections for clarity.
            Present important insights in bullet points.
            Clear, structured formatting using:
            ## for main sections (e.g., Summary of Key Metrics, Patterns & Trends, Key Relationships).
            Bold () for important metrics.
            Keep response under 20-30 words. Avoid excessive detail and unnecessary elaboration.
            Warnings:

            Avoid company identifiers.
            Avoid phrases like "it looks like" or "it seems".
            Do not include unnecessary details, focus on critical insights only.

        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
                        You are a data analyst. Format your analysis with:
                        - Markdown formatting
                        - ## for main sections
                        - Bold (**) for important metrics
                        - Hierarchical organization
                        - Concise paragraphs
                        Focus on significant findings and critical issues first.
                        For Generator Fuel Consumption, note that 0.0 is not a malfunction.
                    """},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            analysis_text = response.choices[0].message.content.strip()
            
            # Ensure consistent formatting
            if not analysis_text.startswith('•') and not analysis_text.startswith('#'):
                analysis_text = '• ' + analysis_text
            
            return analysis_text
        except Exception as e:
            return f"Analysis error: {str(e)}"

    def build_context_prompt(self, conversation_history):
        """
        Convert conversation history into a context string for the model.
        """
        context_lines = []
        for entry in conversation_history:
            if 'bot_response' in entry and entry['bot_response']:
                context_entry = {
                    "user_query": entry.get('user_query', ''),
                    "results": entry['bot_response'].get('results', []),
                    "analysis": entry['bot_response'].get('analysis', '')
                }
                
                context_lines.append(f"Previous Interaction: {json.dumps(context_entry)}")
        
        # Limit context to last 5 entries
        context_lines = context_lines[-5:]
        
        return "Conversation Context:\n" + "\n".join(context_lines)
