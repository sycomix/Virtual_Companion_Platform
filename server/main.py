from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
from flask_socketio import SocketIO
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
import base64
import requests
import openai
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

from supabase_init import supabase
from conversation import get_conversation

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
CORS(app) # Apply CORS to the app
socketio = SocketIO(app, cors_allowed_origins="*") # Enable WebSockets

# Configure OpenAI API Key
openai_api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = openai_api_key

# Global dictionary to store chat sessions
chat_sessions = {}

def url_to_base64(url):
    response = requests.get(url)
    image_base64 = base64.b64encode(response.content).decode('utf-8')
    return f"data:image/png;base64,{image_base64}"

@app.route('/create-image', methods=['POST'])
def create_image():
    # Get name and description from the request
    name = request.json.get('name')
    description = request.json.get('description')

    chat = ChatOpenAI(model_name='gpt-4')
    summary = chat([HumanMessage(content=f"Create a short prompt for DALL-E using the following description. Make sure to keep the prompt below 10 words: {description}")]).content
    summary = f"Hyper realistic picture. {summary}"

    print(summary)

    # Call DALL-E API to generate an image (Note: Replace this with an actual call to DALL-E)
    response = openai.Image.create(
      prompt=summary,
      n=1,
      size='256x256'
    )
    image_url = response['data'][0]['url']

    # Convert the image to base64
    image_base64 = url_to_base64(image_url)

    return jsonify({"message": "Image created successfully", "base64": image_base64})

@app.route('/generate-realistic-character', methods=['POST'])
def generate_realistic_character():
    chat = ChatOpenAI(model_name='gpt-4')

    content = """
    Instruction:
    - Generate a name and a description for a realistic character.
    - The description should be in bullet-points.
    - The description should describe the physical attributes, the personality, the background story, speech and behavioural patterns, and the conversation style of the character.
    - Output the name and the description in the following format: \"Name: NAME HERE | Description: DESCRIPTION HERE\"
    - Do not output any other text.
    """

    summary = chat([HumanMessage(content=content)]).content

    [name, description] = summary.split('|', 1)
    name = name.replace('Name:', '').strip()
    description = description.replace('Description:', '').strip()

    return jsonify({"message": "Realistic character created successfully", "name": name, "description": description})

@app.route('/generate-fantasy-character', methods=['POST'])
def generate_fantasy_character():
    chat = ChatOpenAI(model_name='gpt-4')

    content = """
    Instruction:
    - Generate a name and a description for a popular, mainstream fantasy character.
    - The description should be in bullet-points.
    - The description should describe the physical attributes, the personality, the background story, speech and behavioural patterns, and the conversation style of the character.
    - Output the name and the description in the following format: \"Name: NAME HERE | Description: DESCRIPTION HERE\"
    - Do not output any other text.
    """

    summary = chat([HumanMessage(content=content)]).content

    [name, description] = summary.split('|', 1)
    name = name.replace('Name:', '').strip()
    description = description.replace('Description:', '').strip()

    return jsonify({"message": "Fantasy character created successfully", "name": name, "description": description})

@socketio.on('start_chat')
def start_chat(data):
    session_id = request.sid
    user_id = data['user_id']
    companion_id = data['companion_id']
    chat_sessions[session_id] = {'conversation': get_conversation(user_id, companion_id)}
    # Emit the session key to the specific client that started the chat
    socketio.emit('session_key', {'session_key': session_id}, room=session_id)

@socketio.on('send_message')
def send_message(data):
    session_id = request.sid
    if chat_session := chat_sessions.get(session_id):
        user_message = data['message']
        companion_message = chat_session['conversation'].run(user_message)

        # Store in Supabase (assuming companion_id is provided in data)
        user_id = data['user_id']
        companion_id = data['companion_id']
        insert_data = {
            'user_id': user_id,
            'companion_id': companion_id,
            'user_message': user_message,
            'companion_message': companion_message
        }
        supabase.table('chat_logs').insert(insert_data).execute()

        socketio.emit('receive_message', {'message': companion_message}, room=session_id)

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    # Remove the chat session information for the disconnected client
    chat_sessions.pop(session_id, None)
    print(f'Session {session_id} disconnected')
