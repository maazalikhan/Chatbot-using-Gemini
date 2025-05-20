from flask import jsonify, request, session, render_template
from flask_session import Session
from init import create_flask_app, initialize_services, setup_logging
from openai import OpenAI
from buildsql import SQLBuilder
from analysis import DataAnalyzer
from history import ConversationHistory
from metadata_loader import MetadataLoader
from logs import QueryLogger
from chathandler import ChatHandler
import uuid
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Set up logging
logger = setup_logging()

# Create Flask app
app = create_flask_app()

# Initialize services
services = initialize_services()

# Initialize OpenAI client
client = OpenAI(api_key="OPEN API KEY")
# Initialize Metadata Loader
metadata_loader = MetadataLoader(services['storage_client'])
metadata = metadata_loader.load_metadata_from_gcs('metadata_siteinfra', 'testingmeta.json')
metadata = metadata_loader.get_metadata()

# Initialize Query Logger
query_logger = QueryLogger(services['bigquery_client'])

chat_handler = ChatHandler(client, query_logger)

# Initialize SQL Builder
sql_builder = SQLBuilder(
    services['bigquery_client'],
    client
)

# Initialize Data Analyzer
data_analyzer = DataAnalyzer(client)

@app.route("/")
def home():
    return render_template("index.html")

@app.route('/ask', methods=['POST'])
@app.route('/ask', methods=['POST'])
def ask():
    try:
        # Get user query
        data = request.get_json(force=True)
        user_query = data.get('message', '')

        logger.info(f"Received query: {user_query}")

        if not user_query:
            return jsonify({"error": "No message provided"}), 400

        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        # Handle the query using the improved ChatHandler
        response = chat_handler.handle_query(user_query, session['session_id'])

        # If it's a data query, proceed with SQL generation and analysis
        if response['type'] == 'data':
            # Get conversation history for context
            context = {
                'conversation_history': query_logger.get_context_history(session['session_id'])
            }

            # Generate SQL query
            query = sql_builder.generate_sql_query(
                user_query,
                metadata,
                context
            )

            # Execute query
            results_df = sql_builder.execute_query(query)

            # Analyze results
            analysis = data_analyzer.analyze_data(
                results_df,
                user_query,
                results_df
            )

            # Log the interaction
            query_logger.log_query(
                session_id=session['session_id'],
                user_query=user_query,
                generated_sql=query,
                analysis=analysis
            )

            return jsonify({
                "type": "analysis",
                "results": results_df.head(3).to_dict(orient='records') if results_df is not None else [],
                "analysis": analysis,
                "query": query
            })
        else:
            # For non-data queries, return the response directly
            return jsonify({
                "type": response['type'],
                "response": response['response'],
                "query": None,
                "results": []
            })

    except Exception as e:
        logger.error(f"Error in ask route: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    history_manager = ConversationHistory(session)
    history = history_manager.get_history()
    return jsonify({
        "conversation_history": history,
        "total_entries": len(history)
    })

@app.route('/clear_history', methods=['POST'])
def clear_history():
    history_manager = ConversationHistory(session)
    total_cleared = history_manager.clear_history()
    return jsonify({
        "status": "History cleared",
        "total_entries": total_cleared
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, use_reloader=False)
