from datetime import datetime
from enum import Enum
from typing import Dict, Any

class QueryType(Enum):
    CHAT = "CHAT"
    DATA = "DATA"
    DEFINITION = "DEFINITION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"

class ChatHandler:
    def __init__(self, openai_client, query_logger):
        self.client = openai_client
        self.query_logger = query_logger

    def determine_query_type(self, query: str) -> QueryType:
        """Determine the type of query using LLM classification."""
        messages = [
            {"role": "system", "content": """
            Classify the query into one of these categories:
            - CHAT: General conversation, greetings, or small talk
            - DATA: Queries about site metrics, performance, or comparisons
            - DEFINITION: Requests for definitions or explanations of technical terms
            - OUT_OF_SCOPE: Questions about unrelated topics (politics, general knowledge, etc.)
            
            Respond with only the category name.
            """},
            {"role": "user", "content": f'"{query}"'}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=messages,
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().upper()
            return QueryType(result)
        except ValueError:
            # If the response doesn't match any QueryType, default to OUT_OF_SCOPE
            return QueryType.OUT_OF_SCOPE
        except Exception as e:
            print(f"Error in determine_query_type: {e}")
            return QueryType.OUT_OF_SCOPE

    def handle_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle all types of queries based on their classification."""
        query_type = self.determine_query_type(query)
        
        handlers = {
            QueryType.CHAT: self._handle_chat,
            QueryType.DATA: self._handle_data,
            QueryType.DEFINITION: self._handle_definition,
            QueryType.OUT_OF_SCOPE: self._handle_out_of_scope
        }
        
        handler = handlers.get(query_type)
        response = handler(query, session_id)
        
        # Log the interaction
        self.query_logger.log_query(
            session_id=session_id,
            user_query=query,
            analysis=response.get('response', '')
        )
        
        return response

    def _handle_chat(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle conversational queries."""
        messages = [
            {"role": "system", "content": 
                f"You are AxInBot, an AI assistant for EdgePoint's telecommunications infrastructure. "
                f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. "
                "When users ask about a site, provide data from the previous day (day minus one). "
                "Respond naturally and helpfully, without mentioning company ID or name. "
                "Keep responses direct and short."
            },
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=messages,
                max_tokens=100
            )
            return {
                "type": "conversation",
                "response": response.choices[0].message.content.strip()
            }
        except Exception as e:
            print(f"Error in _handle_chat: {e}")
            return {
                "type": "error",
                "response": "I apologize, but I encountered an error processing your request."
            }

    def _handle_definition(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle definition/explanation queries."""
        messages = [
            {"role": "system", "content": 
                "You are a technical expert in telecommunications infrastructure. "
                "Provide clear, concise definitions and explanations for technical terms. "
                "Focus on practical relevance to telecom infrastructure. Keep responses short"
            },
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=messages,
                max_tokens=100
            )
            return {
                "type": "definition",
                "response": response.choices[0].message.content.strip()
            }
        except Exception as e:
            print(f"Error in _handle_definition: {e}")
            return {
                "type": "error",
                "response": "I apologize, but I encountered an error explaining this term."
            }

    def _handle_data(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle data analysis queries - return None to let main app handle it."""
        return {
            "type": "data",
            "response": None
        }

    def _handle_out_of_scope(self, query: str, session_id: str) -> Dict[str, Any]:
        """Handle out-of-scope queries."""
        return {
            "type": "out_of_scope",
            "response": "I apologize, but this query is outside my scope. I can help you with telecommunications infrastructure data, technical definitions, and related questions."
        }
