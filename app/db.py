from sqlalchemy import create_engine, event, Index
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from .models import TextEmbedding
from sqlalchemy.ext.declarative import declarative_base

# Database URL (update this with your actual database connection string)
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:marci@localhost:5432/kingdom"

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to create the extension when the database connection is established
def create_extension_on_connect(dbapi_connection, connection_record):
    with dbapi_connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        dbapi_connection.commit()

# Attach the function to the engine's "connect" event
event.listen(engine, "connect", create_extension_on_connect)

# Create an index for the TextEmbedding table
def create_text_embedding_index():
    try:
        # Check if the TextEmbedding table exists
        if engine.dialect.has_table(engine, "text_embeddings"):
            # Define the index for the 'embedding' column in the TextEmbedding table
            index = Index(
                "indexing_vectors",
                TextEmbedding.embedding,
                TextEmbedding.email_account_id,
                TextEmbedding.file_id,
                postgresql_using="hnsw",
                postgresql_with={"m": 16, "ef_construction": 64},
                postgresql_ops={"embedding": "vector_12_ops"},
            )
            # Create the index
            index.create(engine)
            print("Index for TextEmbedding table created successfully.")
        else:
            print("TextEmbedding table does not exist.")
    except ProgrammingError as e:
        print(f"Error creating index: {e}")

# Create the tables in the database if they don't already exist
Base = declarative_base()

def create_all_tables():
    Base.metadata.create_all(engine)
    create_text_embedding_index()  # Create the index after the tables are created

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
