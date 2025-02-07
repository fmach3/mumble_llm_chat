import re
import requests
import time
import logging
from pymumble.pymumble_py3 import Mumble

# Configuration for Mumble server
MUMBLE_SERVER = "192.168.42.254"  # Mumble server IP
MUMBLE_PORT = 64738               # Default Mumble port
MUMBLE_USERNAME = "ChatBot"       # Bot's username
MUMBLE_PASSWORD = ""              # Password (if required)
MUMBLE_CHANNEL = "Root"           # Default channel to join

# Configuration for llama.cpp API
LLAMA_API_URL = f"http://{MUMBLE_SERVER}:8080/completion"  # Local ChatGPT-like API endpoint

# Instructions for the chatbot
INSTRUCTIONS = """
You are a Mumble Server Chatbot. Your task is to assist users and manage the Mumble server. 
You can perform the following actions:
- Respond to user messages in a friendly and helpful manner.
- Execute server commands when requested. Available commands:
  - /move <username> <channel>: Move a user to a specific channel.
  - /mute <username>: Mute a user.
  - /unmute <username>: Unmute a user.
  - /kick <username>: Kick a user from the server.
  - /help: List available commands.
If a user requests a command, respond with the command in the format: COMMAND:<command>.
Example: COMMAND:/move John General
"""

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("mumble_chatbot.log"), logging.StreamHandler()]
)

def generate_response(prompt):
    """
    Generates a response using the locally hosted ChatGPT-like API.
    """
    payload = {
        "prompt": f"{INSTRUCTIONS} {prompt}",
        "temperature": 0.7,
        "max_tokens": 150,
    }
    try:
        response = requests.post(LLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json().get("content", "").strip() if response.json() else None
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to generate response: {e}")
        return None

def execute_command(command):
    """
    Executes a server command based on the LLM's response.
    """
    try:
        if command.startswith("COMMAND:"):
            command = command.replace("COMMAND:", "").strip()
            parts = command.split()
            action = parts[0].lower()

            if action == "/move" and len(parts) == 3:
                username, channel = parts[1], parts[2]
                user = mumble.users.find_by_name(username)
                target_channel = mumble.channels.find_by_name(channel)
                if user and target_channel:
                    user.move(target_channel["channel_id"])
                    logging.info(f"Moved {username} to {channel}.")
                else:
                    logging.error(f"User {username} or channel {channel} not found.")

            elif action == "/mute" and len(parts) == 2:
                username = parts[1]
                user = mumble.users.find_by_name(username)
                if user:
                    user.mute()
                    logging.info(f"Muted {username}.")
                else:
                    logging.error(f"User {username} not found.")

            elif action == "/unmute" and len(parts) == 2:
                username = parts[1]
                user = mumble.users.find_by_name(username)
                if user:
                    user.unmute()
                    logging.info(f"Unmuted {username}.")
                else:
                    logging.error(f"User {username} not found.")

            elif action == "/kick" and len(parts) == 2:
                username = parts[1]
                user = mumble.users.find_by_name(username)
                if user:
                    user.kick()
                    logging.info(f"Kicked {username}.")
                else:
                    logging.error(f"User {username} not found.")

            elif action == "/help":
                help_message = """
                Available commands:
                - /move <username> <channel>: Move a user to a specific channel.
                - /mute <username>: Mute a user.
                - /unmute <username>: Unmute a user.
                - /kick <username>: Kick a user from the server.
                - /help: List available commands.
                """
                mumble.channels.find_by_name(MUMBLE_CHANNEL).send_text_message(help_message)
                logging.info("Displayed help message.")

            else:
                logging.error(f"Invalid command: {command}")

    except Exception as e:
        logging.error(f"Failed to execute command: {e}")

def on_message_received(message):
    """
    Callback function triggered when a message is received in the Mumble chat.
    """
    user = message.actor
    text = message.message.strip()

    # Ignore messages from the bot itself
    if user == MUMBLE_USERNAME:
        return

    logging.info(f"Received message from {user}: {text}")

    # Generate a response using the ChatGPT-like API
    response = generate_response(text)
    if response:
        logging.info(f"Generated response: {response}")

        # Check if the response is a command
        if response.startswith("COMMAND:"):
            execute_command(response)
        else:
            # Send the response back to the Mumble chat
            try:
                mumble.channels.find_by_name(MUMBLE_CHANNEL).send_text_message(response)
            except Exception as e:
                logging.error(f"Failed to send message to Mumble: {e}")
    else:
        logging.warning("No response generated or API request failed.")

def connect_to_mumble():
    """
    Connects to the Mumble server and sets up the bot.
    """
    global mumble
    try:
        mumble = Mumble(MUMBLE_SERVER, MUMBLE_USERNAME, port=MUMBLE_PORT, password=MUMBLE_PASSWORD)
        mumble.callbacks.set_callback("text_received", on_message_received)

        # Connect to the server
        mumble.start()
        mumble.is_ready()

        logging.info(f"Connected to Mumble server as {MUMBLE_USERNAME}.")
    except Exception as e:
        logging.error(f"Failed to connect to Mumble server: {e}")
        raise

def main():
    """
    Main function to run the Mumble chatbot.
    """
    global mumble
    retry_attempts = 5
    attempt = 0
    while attempt < retry_attempts:
        try:
            # Connect to the Mumble server
            connect_to_mumble()

            # Keep the bot running
            while True:
                time.sleep(1)
            break  # Exit the loop after successful connection
        except KeyboardInterrupt:
            logging.info("Bot shutting down...")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            attempt += 1
            if attempt < retry_attempts:
                logging.info(f"Retrying connection... (Attempt {attempt + 1} of {retry_attempts})")
                time.sleep(5)  # Wait 5 seconds before retrying
            else:
                logging.error("Max retry attempts reached. Exiting.")
                break
        finally:
            if mumble:
                mumble.stop()

if __name__ == "__main__":
    main()
