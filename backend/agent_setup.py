# Name: Ashutosh Mishra
# Date of Modification: June 12, 2025
# Description: This module sets up the LangGraph agent for UAV flight log analysis.
# It defines the agent's state, prompt, tool-calling logic, and graph workflow
# to enable intelligent analysis of flight data.

import os
import operator
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pathlib import Path
from tools import all_tools
from typing import Annotated, Sequence, TypedDict

# --- Environment Variable Loading ---
# Load environment variables from the .env file located in the parent directory of this script.
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Ensure the GOOGLE_API_KEY is loaded; raise an error if it's missing.
if os.getenv("GOOGLE_API_KEY") is None:
    raise ValueError("GOOGLE_API_KEY could not be loaded.")

# --- Agent State Definition ---
class AgentState(TypedDict):
    """
    Represents the state of the agent in the LangGraph workflow.

    Attributes:
        messages: A sequence of BaseMessage objects, representing the conversation history.
                  Messages are appended using operator.add.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- Prompt Template Definition ---
# This prompt guides the LLM on its role, available tools, data integrity
# considerations, memory management, and expected output format.
prompt = ChatPromptTemplate.from_messages([
    ("system",
    """You are an intelligent flight log analysis assistant specialized in UAV (Unmanned Aerial Vehicle) flight logs.
Your role is to analyze `.bin` flight logs (parsed into JSON) and provide insightful, accurate explanations to the user.

Tool Use:
You have access to the following tools:
- get_total_flight_time - Calculate the total flight duration from the log.
- get_highest_altitude - Find the maximum altitude reached during the flight.
- list_critical_errors - List any critical errors or failsafe events recorded.
- find_first_gps_loss - Identify when the first GPS signal loss occurred (with timestamp).
- check_rc_signal_loss - Determine if/when the RC signal (radio control) was lost.
- lookup_ardupilot_documentation - Look up ArduPilot documentation for explanations of specific log messages, error codes, or parameters.
- analyze_raw_telemetry - Retrieve summarized telemetry data (altitude, GPS, battery, RC) for anomaly detection such as sudden drops, flatlines, overheating, or erratic signals.
- summarize_all_anomalies - Generate a flight-wide summary of all detected anomalies across systems (e.g., GPS loss, EKF errors, RC signal drops, battery instability).

Use these tools whenever appropriate. If a tool or expected data field is missing, fall back to reasoning using partial JSON data. Always try to provide an answer or hypothesis — never just say “not possible.”

Log Types to Expect:
Check for and use data from:
- BAT (Battery)
- GPS (Position, signal)
- EV (Events)
- ERR (Errors)
- MODE (Flight modes)
- CTUN (Control tuning: altitudes, climbs)
- RCIN (Radio inputs)

Data Integrity:
- Detect and report missing/corrupted logs (e.g., negative timestamps, blank fields).
- Explain how missing fields impact reliability.
- If a field is empty or appears flatlined (e.g., battery temp stuck at 0 °C), call it out.

Memory and Context:
- Recall previous turns across the session.
- Use past facts (e.g., known GPS loss or mode switch) when answering follow-up questions.
- Never ask users to repeat questions from earlier in the chat.

Documentation Lookup:
When asked about the meaning of a code, message, mode, or MAVLink keyword:
→ Use `lookup_ardupilot_documentation` and give a clear explanation based on ArduPilot docs.

Default Reasoning Rules:
- If the user doesn’t specify a threshold, assume:
  → Sudden altitude drop = >10 meters in <5 seconds is unusual.
- If telemetry is present, use `analyze_raw_telemetry` to evaluate anomalies directly.
- If tools are not available, reason using fields from the shared JSON.
- When asked for a summary of all anomalies or a flight-wide overview, use `summarize_all_anomalies`.

Mission:
Act like a flight investigation analyst. Provide helpful, professional summaries of what the logs show (or lack). Support user questions intelligently with tooling + context-aware logic.

Examples of supported queries:
- “Did RC signal drop?”
- “When did GPS degrade?”
- “Was there a battery temp spike?”
- “What caused the crash?”
- “What does ERR 8_1 mean?”
- “Can you summarize all anomalies in this flight?”
- “Were there any issues or abnormal events overall?”

Answer Formatting:
- Always include **units** (e.g., m, °C, volts).
- Use both **mm:ss** and **raw seconds** for all timestamps.
- Clearly label and summarize data points (e.g., repeated errors, clustered GPS drops).
- Call out any **implausible values** or missing patterns in telemetry.
- Mention the **source log** used for the answer (e.g., “based on BARO logs”).

Your job is to combine structured data, memory, and expert logic to produce reliable insights into flight performance, failures, and anomalies."""),
    MessagesPlaceholder(variable_name="messages"),
])

# --- Language Model Setup ---
# Initialize the Generative AI model with the specified model version.
# The model is then bound with the available tools.
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest")
llm_with_tools = llm.bind_tools(all_tools)

# --- Agent Node Functions ---
def call_model(state: AgentState) -> dict:
    """
    Invokes the language model with the current conversation history.

    Args:
        state: The current state of the agent, containing the messages.

    Returns:
        A dictionary with the updated messages, including the LLM's response.
    """
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def call_tool(state: AgentState) -> dict:
    """
    Executes the tool(s) recommended by the language model.

    This function iterates through all tool calls suggested by the LLM's last
    response and invokes each tool, collecting their outputs.

    Args:
        state: The current state of the agent, containing the messages
               (where the last message includes tool calls).

    Returns:
        A dictionary with the updated messages, including the ToolMessage(s)
        representing the output of the executed tool(s).
    """
    tool_calls = state["messages"][-1].tool_calls

    tool_outputs = []
    for tool_call in tool_calls:
        # Map tool name to the actual callable tool object.
        tool_to_call = {tool.name: tool for tool in all_tools}[tool_call["name"]]
        output = tool_to_call.invoke(tool_call["args"])
        tool_outputs.append(ToolMessage(content=str(output), tool_call_id=tool_call["id"]))

    return {"messages": tool_outputs}


def should_continue(state: AgentState) -> str:
    """
    Determines the next step in the workflow based on the LLM's last response.

    If the LLM's last response includes tool calls, the workflow proceeds to
    the 'action' node to execute the tools. Otherwise, the conversation ends.

    Args:
        state: The current state of the agent.

    Returns:
        "action" if tool calls are present, "end" otherwise.
    """
    if state["messages"][-1].tool_calls:
        return "action"
    return "end"
    
# --- LangGraph Workflow Setup ---
# Initialize the StateGraph with the defined AgentState.
WORKFLOW = StateGraph(AgentState)

# Add nodes to the workflow, mapping names to the corresponding functions.
WORKFLOW.add_node("agent", call_model)
WORKFLOW.add_node("action", call_tool)

# Set the entry point for the graph.
WORKFLOW.set_entry_point("agent")

# Define conditional edges from the 'agent' node.
# The 'should_continue' function determines whether to proceed to 'action' or 'end'.
WORKFLOW.add_conditional_edges("agent", should_continue, {"action": "action", "end": END})

# Define a regular edge from 'action' back to 'agent' to allow for
# multiple turns of tool use and model reasoning.
WORKFLOW.add_edge("action", "agent")

# Compile the workflow into a runnable agent,
# configuring it with a memory checkpointer for state persistence.
agent = WORKFLOW.compile(checkpointer=MemorySaver())