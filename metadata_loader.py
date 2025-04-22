import json
from google.cloud import storage

class MetadataLoader:
    def __init__(self, storage_client):
        """
        Initialize MetadataLoader with a Google Cloud Storage client
        
        :param storage_client: Initialized Google Cloud Storage client
        """
        self.storage_client = storage_client
        self.metadata = None

    def load_metadata_from_gcs(self, bucket_name, blob_name):
        """Load metadata from Google Cloud Storage and save it to a text file."""
        try:
            print(f"🔃Loading metadata from GCS: bucket={bucket_name}, blob={blob_name}")
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            metadata_json = blob.download_as_text()
            self.metadata = json.loads(metadata_json)


            print(f"✅ Metadata loaded successfully from {blob_name}")
            return True
        except Exception as e:
            print(f"Error loading metadata: {e}")
            return False

    def get_metadata(self):
        """
        Return the loaded metadata
        
        :return: Metadata dictionary
        """
        return self.metadata
