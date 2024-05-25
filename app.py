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

MANAGER_NUMBER =  "77088484148"
BOT_NUMBER = "+14155238886"
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


def is_manager(contact_number):
    return contact_number == MANAGER_NUMBER

def generate_report(period):
    conn = get_db_connection()
    cursor = conn.cursor()

    logging.info('=======================CONNECTED TO DB FOR REPORT GENERATION===============================')
    
    date_filter = {
        "день": "1 DAY",
        "неделя": "7 DAY",
        "месяц": "1 MONTH"
    }

    if period not in date_filter:
        logging.info(f"Invalid period: {period}")
        return None

    period_sql = date_filter[period]
    report = {}

    try:
        for table in ['complaints', 'feedback', 'suggestions']:
            query = f"""
            SELECT COUNT(*) FROM {table}
            WHERE "date" > CURRENT_TIMESTAMP - INTERVAL '{period_sql}'
            """
            cursor.execute(query)
            count = cursor.fetchone()[0]
            report[table] = count

        # Special handling for Orders table as it has a different column name
        order_query = f"""
        SELECT COUNT(*) FROM Orders
        WHERE "orderdate" > CURRENT_TIMESTAMP - INTERVAL '{period_sql}'
        """
        cursor.execute(order_query)
        order_count = cursor.fetchone()[0]
        report['Orders'] = order_count

    except Exception as e:
        logging.error(f"Error in generate_report: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

    return report

def get_summary(period, type):
    conn = get_db_connection()
    cursor = conn.cursor()

    logging.info('=======================CONNECTED TO DB FOR FETCHING DATABASE===============================')

    date_filter = {
        "день": "1 DAY",
        "неделя": "7 DAY",
        "месяц": "1 MONTH"
    }

    column_filter ={
        "complaints": "ComplaintText",
        "suggestions": "SuggestionText",
        "feedback": "FeedbackText"
    }
    column = column_filter[type]

    if period not in date_filter:
        logging.info(f"Invalid period: {period}")
        return None

    period_sql = date_filter[period]
    data = []

    try:
        query = f"""
        SELECT {column} FROM {type}
        WHERE "date" > CURRENT_TIMESTAMP - INTERVAL '{period_sql}'
        """
        cursor.execute(query)
        data = [row[0] for row in cursor.fetchall()]

    except Exception as e:
        logging.error(f"Error in get_complaints: {e}")
        return None
    finally:
        cursor.close()
        conn.close()
    logging.info(f"=======================DATA FETCHED FROM DB==============================={data}")
    return data


def summarize_data(data):
    response = client.chat.completions.create(model="gpt-4-1106-preview",
    messages=[
        {"role": "system", "content": 'Summarize the data. Return answer in russian language'},
        {"role": "user", "content": data}
    ],
    max_tokens=450)

    full_response = response.choices[0].message.content

    return full_response

def format_report_message(report):
    """Formats the report as a message."""
    if report is None:
        return "Не удалось получить отчет за указанный период времени."

    return (
        f"За данный период времени было:\n"
        f"{report.get('complaints', 0)} - жалоб\n"
        f"{report.get('suggestions', 0)} - предложений\n"
        f"{report.get('feedback', 0)} - отзывов\n"
    )


def add_user(user_name, contact_number):
    """Adds a new user to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "INSERT INTO Users (UserName, ContactNumber) VALUES (%s, %s) RETURNING UserID"
    cursor.execute(query, (user_name, contact_number))
    user_id = cursor.fetchone()[0]  # Fetch the generated UserID
    conn.commit()

    cursor.close()
    conn.close()
    return user_id

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

def clear_old_conversations():
    """Clears conversations that are older than 4 hours."""
    current_time = datetime.now()
    cutoff_time = current_time - timedelta(hours=4)
    global conversation_histories

    for user_id, conversations in list(conversation_histories.items()):
        conversation_histories[user_id] = [msg for msg in conversations if msg[0] > cutoff_time]
        if not conversation_histories[user_id]:
            del conversation_histories[user_id]
    
    logging.info("Old conversations cleared.")

def add_message_to_history(user_id, sender, message):
    """Adds a message to the conversation history for a specific user."""
    now = datetime.now()
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    conversation_histories[user_id].append((now, f"{sender}: {message}"))

def get_recent_history(user_id, hours=3):
    """Retrieves the recent conversation history for a specific user."""
    if user_id not in conversation_histories:
        return []
    
    now = datetime.now()
    cutoff_time = now - timedelta(hours=hours)
    return [msg for time, msg in conversation_histories[user_id] if time > cutoff_time]

def generate_answer(query, user_id):
    """Generates an answer for a given query using the GPT model."""
    db = get_db()
    docs = db.similarity_search(query, k=5)
    docs_page_content = "".join([d.page_content for d in docs])

    recent_history = get_recent_history(user_id, 6)
    history_str = "\n".join(recent_history)

    logging.info("\n=============================\n")
    logging.info(f"history_str: {history_str}")
    logging.info("\n=============================\n")
    
    with open('prompt.txt', 'r') as f:
        prompt = f.read().format(docs_page_content, history_str, query)

    logging.info(f"\n{prompt}\n")

    response = client.chat.completions.create(model="gpt-4-1106-preview",
    messages=[
        {"role": "system", "content": prompt},
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


def send_others(response, type, phone_number=None):
    """Sends a summary of the conversation to the manager via WhatsApp."""
    logging.info('Sending summary of complaints, reviews, and suggestions to manager')
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    summary = response['summary']
    history_messages = get_recent_history(phone_number)
    history_str = "\n".join([msg for msg in history_messages])
    if not history_str:
        history_str = "Нет недавней истории чата."

    body = f'Здравствуйте, {type} от номера {phone_number}:\n{summary}'

    client.messages.create(
        from_=f'whatsapp:{BOT_NUMBER}',
        body=body,
        to=f'whatsapp:+{MANAGER_NUMBER}'
    )
 

def send_order(response, phone_number=None):
    """Sends a summary of the order to the manager via WhatsApp."""
    
    logging.info('Sending summary of order to manager')
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    summary = response['summary']
    history_messages = get_recent_history(phone_number)
    history_str = "\n".join([msg for msg in history_messages])
    body = f'Здравствуйте поступил новый заказ на номер {phone_number}:\n{summary}'
    if not history_str:
        history_str = "Нет недавней истории чата."
    client.messages.create(
        from_=f'whatsapp:{BOT_NUMBER}',
        body=body,
        to=f'whatsapp:+{MANAGER_NUMBER}'
    )
    

def send_info(response, phone_number=None):
    """Sends a summary of the order to the manager via WhatsApp."""
    
    logging.info('Sending summary of order to manager')
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    summary = response['summary']
    history_messages = get_recent_history(phone_number)
    history_str = "\n".join([msg for msg in history_messages])
    if not history_str:
        history_str = "Нет недавней истории чата."
    body = f'Здравствуйте, поступил запрос на информацию от номера {phone_number}:\n{summary}'
    client.messages.create(
        from_=f'whatsapp:{BOT_NUMBER}',
        body=body,
        to=f'whatsapp:+{MANAGER_NUMBER}'
    )
    
    

scheduler = BackgroundScheduler()
scheduler.add_job(func=clear_old_conversations, trigger="interval", hours=4)
scheduler.start()

@app.route("/chatgpt", methods=["POST"])
def chatgpt():
    """Endpoint for handling incoming WhatsApp messages and responding via ChatGPT."""
    try:
        start_time = datetime.now()
        wa_id = request.values.get("WaId", "")
        profile_name = request.values.get("ProfileName", "")
        incoming_msg = request.values.get("Body", "").lower()
        logging.info(f"Received message from {wa_id}: {incoming_msg}")

        # Check if the sender is the manager
        if is_manager(wa_id):
            # Process manager-specific commands
            if incoming_msg in ["день", "неделя", "месяц"]:
                print(wa_id, "is manager")
                report = generate_report(incoming_msg)
                report_message = format_report_message(report)
                logging.info(f'=========================REPORT========================\n{report_message}')

                client = Client(ACCOUNT_SID, AUTH_TOKEN)
                client.messages.create(
                    from_=f'whatsapp:{BOT_NUMBER}',
                    body=f'{report_message}',
                    to=f'whatsapp:+{wa_id}'
                )
                return 'Message sent to manager.'
            
            elif incoming_msg in ["опиши жалобы", "опиши предложения", "опиши отзывы"]:
                print(wa_id, "is manager")
                if incoming_msg == "опиши жалобы":
                    type = "complaints"
                elif incoming_msg == "опиши предложения":
                    type = "suggestions"
                elif incoming_msg == "опиши отзывы":
                    type = "feedback"

                summary = get_summary("день", type)
                summary_text = summarize_data("\n".join(summary))

                client = Client(ACCOUNT_SID, AUTH_TOKEN)
                client.messages.create(
                    from_=f'whatsapp:{BOT_NUMBER}',
                    body=f'{summary_text}',
                    to=f'whatsapp:+{wa_id}'
                )
                return 'Message sent to manager.'
            else:
                return str(MessagingResponse().message("Invalid request. Please send 'День', 'Неделя', or 'Месяц' for a report."))

        # Handle regular user interaction
        add_message_to_history(wa_id, "Customer", incoming_msg)
        
        # Generate the answer using GPT-4
        logging.info(f"Generating answer for query: {incoming_msg}")
        response = generate_answer(incoming_msg, wa_id)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()  
        logging.info(f"==================Response TIME FROM GPT==================: {duration}")
        logging.info(f"Response from generate_answer: {response}")
        answer = response['message_to']
        logging.info(f"BOT Answer: {answer}")
        add_message_to_history(wa_id, "Bot", answer)

        if response['status'] == 'done':
            user_name = profile_name 
            contact_number = wa_id 
            user_id = add_user(user_name, contact_number)
            summary = response['summary']
            current_time = datetime.now()
            if response['type'] == 'Suggestion':
                store_suggestion(user_id, summary, current_time)
                send_others(response, type='поступило предложение', phone_number=wa_id)
            elif response['type'] == 'Complaint':
                store_complaint(user_id, summary, current_time)
                send_others(response,  type='поступила жалоба', phone_number=wa_id)
            elif response['type'] == 'Review':
                store_review(user_id, summary, current_time)
                send_others(response, type='поступил отзыв', phone_number=wa_id)
            elif response['type'] == 'Order':
                # Store the order details
                order_details = response['summary'] 
                order_date = datetime.now()
                store_order(user_id, order_details, order_date)
                send_order(response, phone_number=wa_id)
            elif response['type'] == 'Information':
                send_info(response, phone_number=wa_id)

        if duration > 15:
            client = Client(ACCOUNT_SID, AUTH_TOKEN)
            client.messages.create(
                from_=f'whatsapp:{BOT_NUMBER}',
                body=f'{answer}',
                to=f'whatsapp:+{wa_id}'
            )
            logging.info(f"========================MESSAGE SENT USING A HARDCODE SEND======================")
            return 'Message sent successfully.'

        bot_resp = MessagingResponse()
        bot_resp.message(answer)
        return str(bot_resp)

    except Exception as e:
        logging.error(f"Error in chatgpt function: {e}")
        return str(MessagingResponse().message("Sorry, an error occurred. Please try again."))
    
if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", debug=False, port=8000)
    finally:
        # Shut down the scheduler when exiting the app
        scheduler.shutdown()

