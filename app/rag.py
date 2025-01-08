
from langchain_text_splitters import RecursiveCharacterTextSplitter

from fastembed import TextEmbedding


embeddings = TextEmbedding( model_name= "BAAI/bge-large-en-v1.5" )
print(f"Embedding model: {embeddings.model}")

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)

