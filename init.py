import os
import logging
import secrets
from flask import Flask
from flask_session import Session
from flask_cors import CORS
from google.cloud import bigquery, storage
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()



def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app_debug.log')
        ]
    )
    return logging.getLogger(__name__)

def create_flask_app():
    """Initialize and configure Flask application."""
    app = Flask(__name__)
    
    # Configure session
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True

    # Initialize Flask-Session
    Session(app)

    # Configure CORS
    CORS(app, resources={
        r"/ask": {
            "origins": ["*"],
            "methods": ["POST"],
            "allow_headers": ["Content-Type"]
        }
    }, supports_credentials=True)

    return app

def initialize_services():
    """Initialize required services."""
    # Environment Variables
    OPENAI_API_KEY = "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"
 
    BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "edgepointprod")
    BIGQUERY_DATASET_ID = os.getenv("BIGQUERY_DATASET_ID", "Axin_Data")

    # Create clients
    storage_client = storage.Client()
    bigquery_client = bigquery.Client(project=BIGQUERY_PROJECT_ID)

    return {
        'storage_client': storage_client,
        'bigquery_client': bigquery_client,
        'project_id': BIGQUERY_PROJECT_ID,
        'openai_api_key': OPENAI_API_KEY
    }
