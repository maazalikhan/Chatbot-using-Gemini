# history.py
from datetime import datetime

class ConversationHistory:
    def __init__(self, session):
        """
        Initialize conversation history management
        
        :param session: Flask session object
        """
        self.session = session

    def initialize_history(self):
        """
        Ensure conversation history exists in session
        """
        if 'conversation_history' not in self.session:
            self.session['conversation_history'] = []

    def add_entry(self, user_query, bot_response):
        """
        Add a new entry to the conversation history
        
        :param user_query: User's input query
        :param bot_response: Bot's response
        """
        conversation_entry = {
            'user_query': user_query,
            'bot_response': bot_response,
            'timestamp': datetime.now().isoformat()
        }

        # Add entry to conversation history
        self.session['conversation_history'].append(conversation_entry)
        
        # Mark session as modified
        self.session.modified = True

    def get_history(self):
        """
        Retrieve full conversation history
        
        :return: List of conversation history entries
        """
        return self.session.get('conversation_history', [])

    def clear_history(self):
        """
        Clear entire conversation history
        """
        self.session['conversation_history'] = []
        self.session.modified = True
        return len(self.session['conversation_history'])