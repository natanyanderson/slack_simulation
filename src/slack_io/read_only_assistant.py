"""
Read-only Slack API assistant.
Handles user queries via DM, @mention, or slash commands using GPT-4o with function calling.
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from .tools import (
    get_router,
    TOOL_DEFINITIONS,
    get_planning_prompt
)
from .slack_client import app as bolt_app

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("MODEL_NAME", "gpt-4o")  # Use gpt-4o for function calling

# Get router instance
router = get_router()

# System prompt for the assistant
ASSISTANT_SYSTEM_PROMPT = f"""You are a helpful Slack assistant that can answer questions about the workspace using read-only tools.

{get_planning_prompt()}

When answering questions:
- Use tools to gather information before responding
- Provide clear, concise answers
- Include relevant details like channel names, user names, timestamps

**IMPORTANT - Tool Result Handling:**
- Check the tool result's "success" field first
- If success is true: Use the "data" field to answer the question. Do NOT say you're unable to retrieve data.
- If success is false: Check the "error.message" field and use that exact message to explain the issue to the user.
- Never say "I'm unable to retrieve" or "technical issue" unless the tool explicitly returns success: false with an error.

- For search results, summarize key findings
- For message history, provide context and highlights
- For channel lists, list the channel names and brief details

Always be helpful and respect user privacy.
"""


def execute_tool_call(tool_call, user_id: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute a tool call from GPT-4o.
    
    Args:
        tool_call: Tool call object from GPT-4o (ChatCompletionMessageFunctionToolCall)
        user_id: Slack user ID making the request
        channel_id: Channel ID where the request came from
    
    Returns:
        Tool execution result formatted for GPT-4o
    """
    # Access attributes directly (tool_call is an object, not a dict)
    tool_name = tool_call.function.name
    arguments_str = tool_call.function.arguments
    tool_call_id = tool_call.id
    
    try:
        # Parse arguments
        arguments = json.loads(arguments_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool arguments: {arguments_str}, error: {e}")
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": json.dumps({
                "success": False,
                "error": {
                    "type": "invalid_arguments",
                    "message": f"Failed to parse arguments: {str(e)}"
                }
            })
        }
    
    # Execute tool via router
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
    result = router.execute_tool(
        tool_name=tool_name,
        params=arguments,
        user_id=user_id,
        channel_id=channel_id
    )
    
    # Format result for GPT-4o
    # Ensure the result is properly formatted
    try:
        content = json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Error serializing tool result: {e}")
        # Return a minimal error response if serialization fails
        content = json.dumps({
            "success": False,
            "error": {
                "type": "serialization_error",
                "message": f"Error formatting tool response: {str(e)}",
                "tool": tool_name
            },
            "data": None
        })
    
    return {
        "tool_call_id": tool_call_id,
        "role": "tool",
        "content": content
    }


def handle_user_query(
    user_query: str,
    user_id: str,
    channel_id: Optional[str] = None,
    thread_ts: Optional[str] = None,
    max_iterations: int = 5
) -> Dict[str, Any]:
    """
    Handle a user query using GPT-4o with function calling.
    
    Args:
        user_query: The user's question/request
        user_id: Slack user ID
        channel_id: Channel ID (None for DM)
        thread_ts: Thread timestamp if in a thread
        max_iterations: Maximum number of tool call iterations
    
    Returns:
        {
            "text": str,  # Final answer text
            "tool_calls": int,  # Number of tool calls made
            "success": bool,
            "error": Optional[str]
        }
    """
    try:
        # Initialize conversation
        messages = [
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]
        
        tool_calls_count = 0
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call GPT-4o
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto"  # Let model decide when to use tools
            )
            
            message = response.choices[0].message
            
            # Convert message object to dict format for messages list
            # This ensures compatibility with the API on subsequent calls
            message_dict = {
                "role": message.role,
                "content": message.content,
            }
            
            # Add tool_calls if present (convert objects to dicts)
            if message.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            messages.append(message_dict)
            
            # Check if model wants to call tools
            if message.tool_calls:
                tool_calls_count += len(message.tool_calls)
                
                # Execute all tool calls
                for tool_call in message.tool_calls:
                    tool_result = execute_tool_call(tool_call, user_id, channel_id)
                    messages.append(tool_result)
                
                # Continue loop to get model's response to tool results
                continue
            else:
                # Model has finished (no more tool calls, has final answer)
                final_text = message.content or "I'm sorry, I couldn't generate a response."
                
                return {
                    "text": final_text,
                    "tool_calls": tool_calls_count,
                    "success": True,
                    "error": None
                }
        
        # Max iterations reached
        return {
            "text": "I'm sorry, I reached the maximum number of tool calls. Please try rephrasing your question.",
            "tool_calls": tool_calls_count,
            "success": False,
            "error": "max_iterations_reached"
        }
    
    except Exception as e:
        logger.error(f"Error handling user query: {e}", exc_info=True)
        return {
            "text": f"I encountered an error: {str(e)}. Please try again.",
            "tool_calls": 0,
            "success": False,
            "error": str(e)
        }


def format_response_for_slack(
    response: Dict[str, Any],
    include_metadata: bool = False
) -> str:
    """
    Format the assistant's response for Slack.
    
    Args:
        response: Response from handle_user_query
        include_metadata: Whether to include tool call metadata
    
    Returns:
        Formatted text for Slack
    """
    text = response.get("text", "No response generated.")
    
    if include_metadata and response.get("tool_calls", 0) > 0:
        text += f"\n\n_(Used {response['tool_calls']} tool call(s) to answer)_"
    
    return text


def handle_dm(event: Dict[str, Any], say) -> None:
    """
    Handle a direct message to the bot.
    
    Args:
        event: Slack event
        say: Slack say function
    """
    user_id = event.get("user")
    channel_id = event.get("channel")  # DM channel ID
    text = event.get("text", "").strip()
    thread_ts = event.get("thread_ts")
    
    if not text:
        say(text="Hi! I can help you search Slack, find channels, look up users, and more. What would you like to know?")
        return
    
    logger.info(f"Handling DM from user {user_id}: {text[:100]}")
    
    # Handle query
    response = handle_user_query(
        user_query=text,
        user_id=user_id,
        channel_id=channel_id,
        thread_ts=thread_ts
    )
    
    # Format and send response
    response_text = format_response_for_slack(response, include_metadata=False)
    
    # Send reply
    try:
        if thread_ts:
            # Reply in thread
            say(text=response_text, thread_ts=thread_ts)
        else:
            # New message
            say(text=response_text)
    except Exception as e:
        logger.error(f"Error sending DM response: {e}", exc_info=True)


def handle_mention(event: Dict[str, Any], say) -> None:
    """
    Handle an @mention of the bot in a channel.
    
    Args:
        event: Slack event
        say: Slack say function
    """
    user_id = event.get("user")
    channel_id = event.get("channel")
    text = event.get("text", "").strip()
    thread_ts = event.get("thread_ts")
    event_ts = event.get("ts")
    
    # Remove bot mention from text
    try:
        bot_user_id = bolt_app.client.auth_test().get("user_id")
        text = text.replace(f"<@{bot_user_id}>", "").strip()
        # Also remove any other mentions that might be in the text
        import re
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    except:
        # If we can't get bot user ID, just strip common patterns
        text = text.replace("@slackbench", "").replace("@SlackBench", "").strip()
    
    if not text:
        say(text="Hi! How can I help you? Try asking me about channels, messages, users, or search the workspace.", thread_ts=event_ts)
        return
    
    logger.info(f"Handling mention from user {user_id} in channel {channel_id}: {text[:100]}")
    
    # Handle query
    response = handle_user_query(
        user_query=text,
        user_id=user_id,
        channel_id=channel_id,
        thread_ts=thread_ts
    )
    
    # Format response
    response_text = format_response_for_slack(response, include_metadata=False)
    
    # Always reply in a thread to avoid channel spam
    try:
        say(text=response_text, thread_ts=event_ts)
    except Exception as e:
        logger.error(f"Error sending mention response: {e}", exc_info=True)


def handle_slash_command(ack, command: Dict[str, Any], respond) -> None:
    """
    Handle a slash command.
    
    Args:
        ack: Slack ack function
        command: Slash command data
        respond: Slack respond function (for ephemeral responses)
    """
    # Acknowledge command immediately
    ack()
    
    user_id = command.get("user_id")
    channel_id = command.get("channel_id")
    text = command.get("text", "").strip()
    
    if not text:
        respond(
            text="Usage: /slackbench <query>\n\nExample: /slackbench search for 'oncall runbook' in #frontend",
            response_type="ephemeral"
        )
        return
    
    logger.info(f"Handling slash command from user {user_id}: {text[:100]}")
    
    # Handle query
    response = handle_user_query(
        user_query=text,
        user_id=user_id,
        channel_id=channel_id
    )
    
    # Format response
    response_text = format_response_for_slack(response, include_metadata=True)
    
    # Send ephemeral response
    try:
        respond(text=response_text, response_type="ephemeral")
    except Exception as e:
        logger.error(f"Error sending slash command response: {e}", exc_info=True)
        respond(
            text=f"Error: {str(e)}",
            response_type="ephemeral"
        )

