from fastapi import FastAPI, Body, Depends, HTTPException, status, File, UploadFile, Header, Request
from sqlalchemy.orm import Session
from .auth import create_user, encode, decode, get_user_by_id, verify_email, login_user, refresh_tokens, logout_user
from .models import Token, User, LoginRequest, EmailAccount, DBFile, TextEmbedding ,HeaderParams
from .db import get_db
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from .auth import SECRET_KEY, ALGORITHM
import os
from .auth import generate_verification_code, hashify, set_conf
from .send_mail import send_email_async
import json
from typing import List
from datetime import timezone
from .extract_text import extract_text_from_file
from .rag import text_splitter, embeddings
from langchain.schema import Document
import os
import numpy as np
from sqlalchemy import select
from fastapi.responses import StreamingResponse
from sqlalchemy import func

app = FastAPI()

origins = [
    "http://localhost:5173/",
    "http://localhost:5173/Productions_Frontend"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to extract headers manually
async def get_headers(request: Request) -> dict:
    authorization = request.headers.get("Authorization")
    x_refresh_token = request.headers.get("X-Refresh-Token")
    x_user_id = request.headers.get("X-User-ID")

    return( 
        HeaderParams(
            access_token=authorization,
            refresh_token=x_refresh_token,
            user_id=x_user_id
        )
    )


@app.post("/create_user")
async def register_page(body: dict, db: Session = Depends(get_db)):
    return await create_user(body, db)


@app.post("/auth/verify_email")
async def do_verify_email(body: dict, db: Session = Depends(get_db)):
    return await verify_email(body, db)


@app.post("/auth/token", response_model=Token)
async def login_for_access_token(body: LoginRequest, db=Depends(get_db)):
    return await login_user(body, db)


@app.post("/auth/refresh", response_model=Token)
async def refresh_access(header_params: HeaderParams = Depends(get_headers), db=Depends(get_db)):
    print(header_params)
    return await refresh_tokens(header_params, db)

@app.post("/auth/logout/{user_id}")
async def logout(user_id:int, header_params: HeaderParams = Depends(get_headers), db=Depends(get_db)):
    await refresh_access(header_params, db)
    return await logout_user(user_id, db)


#######################################################################

@app.post("/app/dashboard/{user_id}")
async def get_dashboard(
    user_id: int,
    header_params: HeaderParams = Depends(get_headers),  # Use the get_headers dependency
    db: Session = Depends(get_db)
):
    tokens = await refresh_tokens(header_params, db)  # Decode and validate the token
    
    user = get_user_by_id(user_id, db)
    if user.biz_emails == 0:
        raise HTTPException(status_code=404, detail="Data not found")
    else:
        user_emails = db.query(EmailAccount).filter(user.id == EmailAccount.user_id).all()
        if user_emails == []:
            user.biz_emails = 0
            db.commit()
            db.refresh(user)
            raise HTTPException(status_code=404, detail="Data not found")
        else:
            user.biz_emails = len(user_emails)
            user_emails_json = [email.__get_json__() for email in user_emails]
            db.commit()
            db.refresh(user)
            payload = {"message": "Connected to biz emails"}
            payload["all_emails"] = user_emails_json
            payload.update(tokens)
            return payload


@app.post("/app/add_user_biz/{user_id}")
async def add_user_biz(
    user_id: int, 
    body: dict, 
    header_params: HeaderParams = Depends(get_headers),  # Use the get_headers dependency
    db: Session = Depends(get_db)
):
    tokens = await refresh_tokens(header_params, db)  # Decode and validate the token
    
    user = get_user_by_id(user_id, db)
    
    biz_email = body.get("biz_email")
    biz_password = body.get("biz_password")
    
    if biz_email is None or biz_password is None or user is None:
        raise HTTPException(status_code=404, detail="Data not found")

    encrypted_biz_password = encode(biz_password)
    verification_code = generate_verification_code()
    hashed_verification_code = hashify(verification_code)

    email_account = EmailAccount(
        user_id=user.id, 
        email_address=biz_email,
        provider="Custom", 
        credentials=encrypted_biz_password,
        verification_hash = hashed_verification_code
    )
    
    db.add(email_account)
    db.commit()
    user.biz_emails += 1
    db.commit()
    db.refresh(user)

    payload = {"message": "Connected to biz email"}
    payload.update(tokens)

    email_body = {
        "title": "Verify your business email works!",  
        "sub_title": "Click on the button below or copy the link to your browser to verify your email",
        "message": f"{os.getenv('FRONT_URL')}/verify_email/{verification_code}/{email_account.id}", 
        "button_text": "Verify",
        "visible_tag": f"{user.first_name}'s Dripity",
        "link": f"{os.getenv('FRONT_URL')}/verify_email/{verification_code}/{email_account.id}"
    }

    conf = set_conf({f"sender": "Dripity on behalf of {biz_email}", "sender_email": biz_email, "sender_password": biz_password, "visible_tag": email_body["visible_tag"]})

    try: 
        await send_email_async(conf=conf, recipient=user.email, email_body=email_body)
    except Exception:
        user.biz_emails -= 1
        db.delete(email_account)
        db.commit()
        db.refresh(user)
        raise HTTPException(status_code=404, detail="The credentials you entered failed during test email sending.")
    
    return payload


@app.delete("/app/delete_email/{email_id}")
async def delete_email(
    email_id: int, 
    header_params:HeaderParams= Depends(get_headers),  # Use the get_headers dependency
    db: Session = Depends(get_db)
):
   
    tokens = await refresh_tokens(header_params, db)  # Decode and validate the token

    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_id).first()

    if email_account is None:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    if email_account.user_id != tokens["user_id"]:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this email account")
    
    db.delete(email_account)
    db.commit()
    
    payload = {"message": "Email account deleted"}
    payload.update(tokens)
    return payload




@app.post("/app/resend_verification_email/{email_id}")
async def resend_verification_email(email_id: int, header_params:HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):

    tokens = await refresh_tokens(header_params, db)

    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_id).first()

    if email_account == None:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    if email_account.verified == True:
        raise HTTPException(status_code=404, detail="This email account has already been verified")
    
    if email_account.user_id!= tokens["user_id"]:
        raise HTTPException(status_code=403, detail="You are not authorized to resend this email account verification email")
    

    user = db.query(User).filter(User.id == tokens["user_id"]).first()

    verification_code = generate_verification_code()
    hashed_verification_code = hashify(verification_code)
    
    email_account.verification_hash = hashed_verification_code
    db.commit()
    
    email_body = {
        "title": "Verify your buisness email works!",  
        "sub_title": "Click on the button below or copy the link to your browser to verify your email",
        "message": f"{os.getenv('FRONT_URL')}/verify_email/{verification_code}/{email_account.id}", 
        "button_text": "Verify",
        "visible_tag": f"{user.first_name}'s Dripity",
        "link": f"{os.getenv('FRONT_URL')}/verify_email/{verification_code}/{email_account.id}"
    }
        

    conf = set_conf({f"sender": "Dripity on behalf of {email_account.email_address}", "sender_email": email_account.email_address, "sender_password": decode(email_account.credentials), "visible_tag": email_body["visible_tag"]})


    try: 
        await send_email_async(conf=conf, recipient= user.email , email_body=email_body)
        
        
    except(Exception):
        user.biz_emails -=1
        db.delete(email_account)
        db.commit()
        db.refresh(user)
        raise HTTPException(status_code=404, detail="The credentials you entered failed during test email sending.")
    
    payload = {"message": "Email sent successfully"}
    
    payload.update(tokens)
    return payload


@app.post("/app/upload_files/{email_id}")
async def upload_files(
    email_id: int,
    files: List[UploadFile] = File(...),
    header_params: HeaderParams = Depends(get_headers),
    db: Session = Depends(get_db),
):
    ALLOWED_CONTENT_TYPES = {
        "application/pdf": "PDF",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
        "application/msword": "DOC",
        "text/plain": "TXT",
    }

    tokens = await refresh_tokens(header_params, db)
    user = db.query(User).filter(User.id == tokens["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_id).first()
    if not email_account or not email_account.verified:
        raise HTTPException(status_code=403, detail="Invalid or unverified email account")

    total_file_size = 0

    for file in files:
        file_size = os.fstat(file.file.fileno()).st_size
        total_file_size += file_size
        if db.query(DBFile).filter(DBFile.email_account_id == email_account.id, DBFile.file_name == file.filename).first():
            raise HTTPException(status_code=400, detail=f"File '{file.filename}' already exists")
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail=f"File type of '{file.filename}' is not allowed")
        if total_file_size + user.storage_used > 1000000000:  # Replace with realistic limit
            raise HTTPException(status_code=413, detail="Total file size exceeds limit")

    for file in files:
        try:
            DB_file = DBFile(
                email_account_id=email_account.id,
                file_name=file.filename,
                file_size=os.fstat(file.file.fileno()).st_size,
                content_type=ALLOWED_CONTENT_TYPES[file.content_type],
            )
            db.add(DB_file)
            db.commit()
            db.refresh(DB_file)

            file_text = await extract_text_from_file(file, file.content_type)
            documents = text_splitter.split_documents([Document(page_content=file_text)])

            all_embeddings = []
            for doc in documents:
                # Generate embedding
                embedding = list(embeddings.embed([doc.page_content]))
                all_embeddings.append((embedding[0], doc.page_content))  # Pair embedding with text

            print(f"Generated {len(all_embeddings)} embeddings for {file.filename}")

            # Insert embeddings into the database
            for embedding, content in all_embeddings:
                print(len(embedding))
                embed = TextEmbedding(
                    filename=file.filename,
                    embedding=embedding,
                    text=content,
                    file_id=DB_file.id,
                    email_account_id=email_account.id,
                )
                db.add(embed)

            db.commit()  # Commit all at once for better performance
            print(f"Inserted {len(all_embeddings)} embeddings for {file.filename} into the database.")

        except Exception as e:
            print(f"Error processing file '{file.filename}': {str(e)}")
            return {"error": f"Error processing file '{file.filename}': {str(e)}"}

    return {"message": "Files processed successfully", "tokens": tokens}



@app.get("/app/see_files/{email_account_id}")
async def see_files(email_account_id: int, header_params: HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):
    tokens = await refresh_tokens(header_params, db)
    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_account_id).first()

    if not email_account:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    files = email_account.files

    if files == []:
        raise HTTPException(status_code=404, detail="Data not found")
    
    else:
        files_json = [file. __get_json__() for file in files]

        payload= {"all_files": files_json}
        payload.update(tokens)

        return payload

@app.delete("/app/delete_file/{email_account_id}/{file_id}")
async def delete_file(email_account_id: int, file_id: int, header_params: HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):
    tokens = await refresh_tokens(header_params, db)
    
    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_account_id).first()
    user = email_account.user
    if not email_account:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    files = email_account.files
    if files == []:
        raise HTTPException(status_code=404, detail="Data not found")
    
    else:
        file = db.query(DBFile).filter(DBFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        else:
            db.delete(file)
            user.storage_used -= file.file_size
            db.commit()
            db.refresh(user)
            payload = {"message": "File deleted successfully"}
            payload.update(tokens)
            return payload


@app.delete("/app/delete_all_files/{email_account_id}")
async def delete_all_files(email_account_id: int, header_params: HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):
    tokens = await refresh_tokens(header_params, db)

    
    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_account_id).first()
    user = email_account.user

    if not email_account:
        raise HTTPException(status_code=404, detail="Email account not found")
    
    files = email_account.files
    if files == []:
        raise HTTPException(status_code=404, detail="Data not found")
    else:
        for file in files:
            db.delete(file)
            db.commit()
            db.refresh(user)

        user.storage_used = 0
        payload = {"message": "All files deleted successfully"}
        payload.update(tokens)
        return payload

        
@app.post("/app/most_relevant_files/{email_account_id}")
async def most_relevant_files(email_account_id: int,  body: dict, header_params: HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):
    tokens = await refresh_tokens(header_params, db)
    
    email_account = db.query(EmailAccount).filter(EmailAccount.id == email_account_id).first()
   
    if not email_account:     #need this to only return values files that are linked to this account
        raise HTTPException(status_code=404, detail="Email account not found") 
    
    if len(body["query"]) > 1000:

        documents = text_splitter.split_documents([Document(page_content=body["query"])])
        generators = embeddings.embed([doc.page_content for doc in documents])
        vectors = [list(generator) for generator in generators]
    
    else:
        vectors = list(embeddings.embed([body["query"]]))

    added_files = set()
    files = []
    files_to_embeddings = {}
    for vector in vectors:
        closest_embeddings = db.scalars(
            select(TextEmbedding)
            .where(TextEmbedding.embedding.l2_distance(vector) <= .8)  # Distance threshold, adjust as needed
            .where(TextEmbedding.email_account_id == email_account_id)
            .order_by(TextEmbedding.embedding.l2_distance(vector))  # Order by smallest distance (most accurate matches)
            .limit(2)  # Limit to 2 closest embeddings
        )

        for emb in closest_embeddings:
            if emb.file_id not in added_files:
                added_files.add(emb.file_id)
                files.append(emb.file.__get_json__())
                files_to_embeddings[emb.file_id] = [emb.text]
            else:
                files_to_embeddings[emb.file_id].append(emb.text)

   
    if len(added_files) == 0:
        payload={"message": "No files found"}
        
    else:
        payload = {"message": "Files found", "files": files, "similar_texts": files_to_embeddings}

    payload.update(tokens)
    return payload

@app.get("/app/get_file/{file_id}")
async def get_file(file_id: int, header_params: HeaderParams = Depends(get_headers), db: Session = Depends(get_db)):
    try:
        tokens = await refresh_tokens(header_params, db)
    except HTTPException as e:
        raise e  
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    
    file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    async def file_text_generator():
        query = (
            db.query(TextEmbedding.text)
            .filter(TextEmbedding.file_id == file_id)
            .order_by(TextEmbedding.id)
        )
        # Use the query iterator
        for row in query.yield_per(50):  # Fetch rows in chunks of 100
            yield row.text + "\n"

    return StreamingResponse(file_text_generator(), media_type="text/plain")














