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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
ZILLIZ_URI = os.getenv("ZILLIZ_URI")
ZILLIZ_USER = os.getenv("ZILLIZ_USER")
ZILLIZ_PASSWORD = os.getenv("ZILLIZ_PASSWORD")


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

