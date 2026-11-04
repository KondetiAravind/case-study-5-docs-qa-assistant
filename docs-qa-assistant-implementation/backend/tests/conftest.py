import os

# Use deterministic embeddings and isolated temporary Chroma collections in tests.
os.environ["APP_ENV"] = "test"
