from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import time
import openai
from twilio.rest import Client
from dotenv import load_dotenv
from urllib.parse import parse_qs

load_dotenv()

# OpenAI API Key
openai_key = os.environ.get('OPENAI_API_KEY')
openai_assistant_id = os.environ.get('OPENAI_ASSISTANT_ID')

# Initialize Twilio client
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
client_twilio = Client(account_sid, auth_token)

# Twilio WhatsApp sandbox number
twilio_whatsapp_number = 'whatsapp:+14155238886'

class MyHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        assistant_id = self.server.assistant_id
        client_openai = self.server.client
        thread = client_openai.beta.threads.create()
        thread_id = thread.id

        if self.path == '/whatsapp':

            post_data = parse_qs(post_data.decode('utf-8'))
            
            print(post_data)

            incoming_msg = post_data.get('Body', [''])[0]
            sender_name = post_data.get('ProfileName', [''])[0]
            sender_number = post_data.get('From', [''])[0].replace('whatsapp:', '')

            # Get GenAI response
            incoming_msg = incoming_msg + " From: " + sender_name
            response = self.process_user_message(client_openai, thread_id, assistant_id, incoming_msg)

            if response is None:
                response = "Failed to process incoming message."

            # Send Whatsapp Message
            self.send_whatsapp_message(sender_number, response)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response_data = json.dumps({'response': response})
            self.wfile.write(response_data.encode('utf-8'))

        else:
            self.send_error(404)


    # Function to send a WhatsApp message
    def send_whatsapp_message(self, recipient_number, message_body):
        print("RECIPIENT NUMBER:" + str(recipient_number))
        message = client_twilio.messages.create(
            body=message_body,
            from_=twilio_whatsapp_number,
            to=f'whatsapp:{recipient_number}'
        )
        print(f"Sent WhatsApp message to {recipient_number}: {message_body}")


    def process_user_message(self, client, thread_id, assistant_id, user_message):
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        run_id = run.id
        run_status = run.status

        while run_status not in ["completed", "failed", "requires_action"]:
            time.sleep(3)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            run_status = run.status

        if run_status == "completed":
            messages = client.beta.threads.messages.list(thread_id=thread_id)
            output = messages.data[0].content[0].text.value
            return output
        elif run_status == "failed":
            print("Run failed.")
            return None

class MyHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, assistant_id, client):
        self.assistant_id = assistant_id
        self.client = client
        super().__init__(server_address, RequestHandlerClass)

def run_server():
    client = openai.OpenAI(api_key=openai_key)

    port = 22222
    server_address = ('', port)
    httpd = MyHTTPServer(server_address, MyHTTPRequestHandler, openai_assistant_id, client)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
