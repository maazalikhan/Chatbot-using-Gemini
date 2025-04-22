import pandas as pd
from google.cloud import storage
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from io import StringIO
import re

class KnownGoodQueries:
    def __init__(self, bucket_name="metadata_siteinfra", file_name="knowngoodqueries.csv"):
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.queries_df = None
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings = None
        # Initialize embeddings after loading queries:
        self.load_queries()
        if self.queries_df is not None and not self.queries_df.empty:
            self.embeddings = self.model.encode(
                self.queries_df['user_query'].str.lower().apply(self.preprocess_query).tolist()
            )


    def load_queries(self):
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(self.bucket_name)
            blob = bucket.blob(self.file_name)
            
            print("🔃Downloading file content...")
            # Download as bytes instead of text
            content_bytes = blob.download_as_bytes()
            content = content_bytes.decode('latin1')
         
            if content is None:
                raise ValueError("❌ Could not decode file with any attempted encoding")
                
            self.queries_df = pd.read_csv(StringIO(content), on_bad_lines='skip')
            print(f"✅Successfully loaded {len(self.queries_df)} queries")

        except Exception as e:
            print(f"Error loading queries {str(e)}")

    def preprocess_query(self, query):
        # Handle None or empty input
        if not query or not isinstance(query, str):
            return ""
            
        # Strip company ID and other metadata
        query = query.split('|')[0] if '|' in query else query
        
        query = query.lower().strip()
        
        # Expanded stopwords removal
        stopwords = ['calculate', 'the', 'number', 'of', 'find', 'show', 
                    'display', 'get', 'me', 'give', 'list']
        pattern = '|'.join(r'\b{}\b'.format(word) for word in stopwords)
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        
        query = re.sub(r'[^\w\s]', '', query)  # Remove punctuation
        query = re.sub(r'\s+', ' ', query)
        
        return query.strip()

    def find_exact_match(self, user_query):
        print(f"\nSearching for exact match for: {user_query}")
        if self.queries_df is None:
            print("❌ No queries loaded")
            return None
            
        preprocessed_query = self.preprocess_query(user_query)
        print(f"Preprocessed user query: {preprocessed_query}")
        
        for idx, known_query in enumerate(self.queries_df['user_query']):
            known_preprocessed = self.preprocess_query(known_query)
            #print(f"\nComparing with known query {idx}:")
            #print(f"Known: {known_preprocessed}")
            #print(f"Match: {known_preprocessed == preprocessed_query}")
            
        exact_match = self.queries_df[self.queries_df['user_query'].str.lower().apply(self.preprocess_query) == preprocessed_query]
        return None if exact_match.empty else exact_match.iloc[0]['sql_query']

    def find_similar_match(self, user_query, similarity_threshold=0.8):
        print(f"\nSearching for similar match for: {user_query}")
        if self.queries_df is None or self.queries_df.empty:
            print("No queries loaded")
            return None

        preprocessed_query = self.preprocess_query(user_query)
    #   print(f"Preprocessed query: {preprocessed_query}")
        
        query_embedding = self.model.encode([preprocessed_query])[0]
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        
        #print("\nSimilarity scores:")
        #for idx, (query, score) in enumerate(zip(self.queries_df['user_query'], similarities)):
            #print(f"{idx}. {query}: {score:.4f}")
            
        best_match_idx = np.argmax(similarities)
        best_score = similarities[best_match_idx]
        #print(f"\nBest match: {self.queries_df.iloc[best_match_idx]['user_query']}")
        #print(f"Score: {best_score:.4f}")
        #print(f"Threshold: {similarity_threshold}")
        
        if best_score >= similarity_threshold:
            return self.queries_df.iloc[best_match_idx]['sql_query']
        
        return None
