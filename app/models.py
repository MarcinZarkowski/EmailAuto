from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
import datetime
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from pgvector.sqlalchemy import Vector
from typing import Optional, Dict
from fastapi import Header
import pgvector
# Number of dimensions for embeddings
N_DIM = 1024


# Base class for models
Base = declarative_base()


class HeaderParams(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None

    




# Token and TokenData Models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    user_id: int

class TokenData(BaseModel):
    email: str | None = None

class LoginRequest(BaseModel):
    email: str
    password: str

# User Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, unique=True, primary_key=True)
    password = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    subscription_level = Column(Integer, default=0)
    date_joined = Column(DateTime, default=datetime.datetime.now)

    storage_used = Column(Integer, default=0)  # In bytes
    verified = Column(Boolean, default=False)
    verification_hash = Column(String(255), nullable=False, default="")
    biz_emails = Column(Integer, default=0)
    refresh = Column(String(255), nullable=True)
    access = Column(String(255), nullable=True)

    # Relationship to EmailAccount (Multiple email accounts per user)
    email_accounts = relationship("EmailAccount", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(name='{self.first_name}', email='{self.email}')>"

# EmailAccount Model
class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(Integer, unique=True, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_address = Column(String(255), unique=True, nullable=False, index=True)
    provider = Column(String(100))
    credentials = Column(LargeBinary)  # Store encrypted credentials (e.g., token, password)
    date_added = Column(DateTime, default=datetime.datetime.now)
    verified = Column(Boolean, default=False)
    verification_hash = Column(String(255), nullable=False)

    # Relationships
    user = relationship("User", back_populates="email_accounts")
    files = relationship("DBFile", back_populates="email_account", cascade="all, delete-orphan")
    embeddings = relationship("TextEmbedding", back_populates="email_account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EmailAccount(email_address='{self.email_address}')>"

    def __get_json__(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_address": self.email_address,
            "verified": self.verified,
            "date_added": self.date_added
        }

# File Model
class DBFile(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    email_account_id = Column(Integer, ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False, index = True)
    file_name = Column(String, index=True, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.now)
    file_size = Column(Integer) # in bytes 
    content_type = Column(String)  # e.g., "text/plain"
   

    #text = Column(String) 

    # Relationship
    email_account = relationship("EmailAccount", back_populates="files")
    embeddings = relationship("TextEmbedding", back_populates="file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<File(filename='{self.filename}', email_account_id='{self.email_account_id}')>"
    def __get_json__(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "uploaded_at": self.uploaded_at
        }

        

# TextEmbedding Model
class TextEmbedding(Base):
    __tablename__ = "text_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)  
    text = Column(String, nullable=False)
    embedding = Column(Vector(N_DIM))
    email_account_id = Column(Integer, ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)  #Duplicat ? since we can access fil_id from TextEmbedding.file.id

    # Relationships
    email_account = relationship("EmailAccount", back_populates="embeddings")
    file = relationship("DBFile", back_populates="embeddings")

    def as_dict(self):
        return {
            "id": self.id,
            "email_account_id": self.email_account_id,
            "filename": self.filename,
            "embedding": self.embedding,
        }

# # EmailData Model - Stores email data for each email account
# class EmailData(Base):
#     __tablename__ = "email_data"
#     id = Column(Integer, primary_key=True)
#     email_account_id = Column(Integer, ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False)
#     subject = Column(String(255))
#     body = Column(String)
#     received_at = Column(DateTime, default=datetime.datetime.now)
#     def __repr__(self):
#         return f"<EmailData(subject='{self.subject}', received_at='{self.received_at}')>"

# UserCustomerEmails Model - Stores email addresses associated with customers
# class UserCustomerEmails(Base):
#     __tablename__ = "user_customer_emails"
#     id = Column(Integer, primary_key=True)
#     email = Column(String(255), unique=True, nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     def __repr__(self):
#         return f"<UserCustomerEmails(email='{self.email}')>"
