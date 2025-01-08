import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
from .models import User 
load_dotenv()

def set_conf( configuration):
    if configuration["sender"] == "Dripity":
        
        conf = ConnectionConfig(
            MAIL_USERNAME=os.getenv("MAIL_ADDRESS"),
            MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
            MAIL_FROM= os.getenv("MAIL_ADDRESS"),
            MAIL_PORT= 587 ,
            MAIL_SERVER=os.getenv("MAIL_SERVER"),
            MAIL_STARTTLS = True, # or False depending on your provider
            MAIL_SSL_TLS = False,
            MAIL_FROM_NAME= configuration["visible_tag"],
            USE_CREDENTIALS=True,
            TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates"),
        )

    else:
        conf = ConnectionConfig(
            MAIL_USERNAME=configuration["sender_email"],
            MAIL_PASSWORD=configuration["sender_password"],
            MAIL_FROM= configuration["sender_email"],
            MAIL_PORT= 587 ,
            MAIL_SERVER=os.getenv("MAIL_SERVER"),
            MAIL_STARTTLS = True, # or False depending on your provider
            MAIL_SSL_TLS = False,
            MAIL_FROM_NAME= configuration["visible_tag"],
            USE_CREDENTIALS=True,
            TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates"),
        )


    return conf




async def send_email_async(conf: ConnectionConfig, recipient:str , email_body: dict):
    
    message = MessageSchema(
        subject=email_body["title"],
        recipients=[recipient],
        template_body=email_body,
        subtype='html',
    )
    
    fm = FastMail(conf)

    await fm.send_message(message, template_name='email.html')



# def send_email_background(conf: ConnectionConfig, recipient:str , email_body: dict):



#     message = MessageSchema(
#         subject=subject,
#         recipients=[recipient],
#         body=body,
#         subtype='html',
#     )
#     fm = FastMail(conf)

#     background_tasks.add_task(fm.send_message, message, template_name='email.html')



