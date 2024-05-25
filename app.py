import os
import json
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler

from langchain_openai import OpenAIEmbeddings
#from langchain.vectorstores import Milvus		#commented because it is old, the langchain_community is  alternative
from langchain_community.vectorstores import Milvus
from dotenv import load_dotenv
import logging

from datetime import datetime

def configure_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

configure_logging()
# Initialize Flask App
app = Flask(__name__)
load_dotenv()

# Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
ZILLIZ_URI = os.getenv("ZILLIZ_URI")
ZILLIZ_USER = os.getenv("ZILLIZ_USER")
ZILLIZ_PASSWORD = os.getenv("ZILLIZ_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")


MANAGER_NUMBER = "77010999911"
BOT_NUMBER = "+77778889221"
try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    logging.info('=========================CONNECTED TO DB POSTGRE=============================')
except Exception:
    logging.info('=====================NOT CONNECTED TO POSTGRE SERVER=========================')

def store_order(user_id, order_details, order_date):
    """Stores an order in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO Orders (UserID, OrderDetails, OrderDate)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (user_id, order_details, order_date))
    conn.commit()
    cursor.close()
    conn.close()

def store_complaint(user_id, complaint_text, complaint_date):
    """Stores a complaint in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO Complaints (UserID, ComplaintText, Date)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (user_id, complaint_text, complaint_date))
    conn.commit()
    cursor.close()
    conn.close()

def store_review(user_id, review_text, review_date):
    """Stores a review in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO Feedback (UserID, FeedbackText, Date)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (user_id, review_text, review_date))
    conn.commit()
    cursor.close()
    conn.close()

def store_suggestion(user_id, suggestion_text, suggestion_date):
    """Stores a suggestion in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO Suggestions (UserID, SuggestionText, Date)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (user_id, suggestion_text, suggestion_date))
    conn.commit()
    cursor.close()
    conn.close()

# Global Variables
conversation_histories = {}

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

def get_db():
    """Connects to the Milvus vector database and returns the connection object."""
    logging.info("Connecting Zilliz")
    embeddings = OpenAIEmbeddings()
    database = Milvus(
        embedding_function=embeddings,
        collection_name="Answers",      
        connection_args={
            "uri": ZILLIZ_URI,
            "user": ZILLIZ_USER,
            "password": ZILLIZ_PASSWORD,
            "secure": True,
        },
        drop_old=False
    )
    logging.info("Success Zilliz Connection")
    return database


def generate_answer(query, user_id):
    """Generates an answer for a given query using the GPT model."""

    logging.info(f"\n{query}\n")

    response = client.chat.completions.create(model="gpt-4-1106-preview",
    messages=[
        {"role": "system", "content": query},
        {"role": "user", "content": query}
    ],
    max_tokens=450)

    full_response = response.choices[0].message.content

    logging.info(f"\n===========================FULL RESPONSE======================\n")
    logging.info(full_response)

    # Find the index of the first opening curly brace
    start_index = full_response.find('{')
    end_index = full_response.find('}')

    # Extract the JSON part from the string starting from the first '{'
    json_str = full_response[start_index:end_index + 1]
    logging.info('\n===========================ADJUSTED RESPONSE======================\n')
    logging.info(json_str)

    # Convert the JSON string to a dictionary
    try:
        full_response_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        logging.info(f"Error decoding JSON: {e}")


    logging.info("\n===========================DICTIONARY======================\n")
    logging.info(full_response_json)
    logging.info("\n===========================================================\n")
    if 'status' not in full_response_json:
        full_response_json['status'] = 'processing'
    return full_response_json


@app.route("/chatgpt", methods=["POST"])
def chatgpt():
    """Endpoint for handling incoming WhatsApp messages and responding via ChatGPT."""
    incoming_msg = request.values.get("Body", "").lower()
    wa_id = request.values.get("WaId", "")
    
    # Generate the answer using GPT-4
    logging.info(f"Generating answer for query: {incoming_msg}")
    response = generate_answer(incoming_msg, wa_id)
    answer = response['message_to']
    logging.info(f"BOT Answer: {answer}")


    return str(answer)



if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, port=8000)

