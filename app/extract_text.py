from fastapi import HTTPException, UploadFile
from docx import Document
import pdfplumber
import io
import asyncio

# Function to read a file asynchronously in chunks
async def read_file_in_chunks(file: UploadFile, chunk_size=1024*1024):  # 1 MB per chunk
    """Asynchronously read the file in chunks to minimize blocking"""
    content = b''
    while chunk := await file.read(chunk_size):
        content += chunk
    return content

# Extract text from PDF file using pdfplumber
async def extract_text_from_pdf(file: UploadFile):
    # Read the file in chunks
    file_content = await read_file_in_chunks(file)
    file_like_obj = io.BytesIO(file_content)
    text = ""

    # Use pdfplumber to extract text
    with pdfplumber.open(file_like_obj) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""  # Avoid appending None if no text is found
    return text

# Extract text from DOCX file
async def extract_text_from_docx(file: UploadFile):
    # Read the file in chunks
    file_content = await read_file_in_chunks(file)
    file_like_obj = io.BytesIO(file_content)
    doc = Document(file_like_obj)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"  # Add new lines for separation of paragraphs
    return text

# Extract text from TXT file (simple text decoding)
async def extract_text_from_txt(file: UploadFile):
    # Read the file in chunks
    file_content = await read_file_in_chunks(file)
    return file_content.decode('utf-8')  # Assuming the file is UTF-8 encoded

# Main function to extract text based on file type
async def extract_text_from_file(file: UploadFile, content_type: str):
    if content_type == 'application/pdf':
        return await extract_text_from_pdf(file)
    elif content_type == 'text/plain':
        return await extract_text_from_txt(file)
    elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return await extract_text_from_docx(file)
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type}")
