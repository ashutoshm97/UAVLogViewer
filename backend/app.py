# Name: Ashutosh Mishra
# Date of Modification: June 12, 2025
# Description: This Flask application serves as the backend for the UAV Log Viewer.
# It handles receiving parsed flight data from the frontend, caching it, and
# processing user chat queries using a LangGraph agent.

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from langchain_core.messages import HumanMessage

# Import the AGENT from agent_setup.py (corrected casing for the agent variable)
from agent_setup import agent
# Import functions for setting and getting flight data from the data_parser module
from data_parser import get_flight_data, set_flight_data

# Initialize the Flask application
app = Flask(__name__)
# Enable Cross-Origin Resource Sharing (CORS) for the app to allow frontend requests
CORS(app)


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    A simple endpoint to verify the backend is running and accessible.

    Returns:
        A JSON response indicating the backend status and an HTTP 200 OK status code.
    """
    return jsonify({"status": "Backend is running!"}), 200


@app.route('/api/set-flight-data', methods=['POST'])
def set_data():
    """
    Receives a large JSON object containing pre-parsed flight data from the frontend.
    This data is then stored in a shared cache variable via the `set_flight_data`
    helper function for use by the LangGraph agent.

    Returns:
        A JSON response indicating success or an error, along with an appropriate
        HTTP status code.
    """
    parsed_data = request.get_json()

    # Validate if data was received
    if not parsed_data:
        return jsonify({"error": "No data received"}), 400

    # Debugging block to print keys received from the JavaScript parser
    print("\n--- BACKEND RECEIVED THESE KEYS FROM JS PARSER ---")
    # Sort keys alphabetically for easy comparison and debugging
    print(sorted(list(parsed_data.keys())))
    print("------------------------------------------------\n")

    # Store the received JSON data in our shared global variable via the helper function
    set_flight_data(parsed_data)
    print("Backend successfully received and cached JS-parsed data from the frontend.")
    return jsonify({"status": "success", "message": "Data cached and agent is ready."}), 200


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handles incoming chat messages from the frontend.
    It first checks if flight data has been cached. If data is present,
    it invokes the LangGraph agent with the user's message and returns
    the agent's response.

    Returns:
        A JSON response containing the agent's reply or an error message,
        along with an appropriate HTTP status code.
    """
    # Ensure flight data has been uploaded and processed before attempting to chat
    if get_flight_data() is None:
        return jsonify({"response": "Please upload and process a log file first."}), 400

    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Configure the LangGraph agent's session (thread) for conversation memory
    config = {"configurable": {"thread_id": "user1_session"}}
    # Prepare the initial state for the agent with the human's message
    input_state = {"messages": [HumanMessage(content=user_message)]}

    try:
        # Invoke the agent with the input state and configuration
        final_state = agent.invoke(input_state, config=config)
        # Extract the content from the last message in the agent's final state
        response = final_state["messages"][-1].content
        return jsonify({"response": response}), 200
    except Exception as e:
        # Catch any exceptions during agent invocation and return an error
        print(f"Error invoking agent: {e}")
        return jsonify({"response": f"An error occurred: {e}"}), 500


if __name__ == '__main__':
    # Run the Flask application in debug mode on port 5000
    # debug=True allows for automatic reloading on code changes and provides a debugger
    app.run(debug=True, port=5000)