"""
Read-only Slack API assistant.
Handles user queries via DM, @mention, or slash commands using GPT-4o with function calling.
"""
import os
import json
import logging
import time
from typing import Dict, Any, Optional, List
from openai import OpenAI
from .tools import (
    get_router,
    TOOL_DEFINITIONS,
    get_planning_prompt
)
from .tools.tracer import get_tracer
# Import slack_client lazily to avoid circular dependencies
# Will be imported only if needed for auth_test()
bolt_app = None

def _get_bolt_app():
    """Lazy import of bolt_app to avoid circular dependencies."""
    global bolt_app
    if bolt_app is None:
        try:
            from .slack_client import get_app
            bolt_app = get_app()
        except (ImportError, Exception):
            pass
    return bolt_app

logger = logging.getLogger(__name__)

# Conversation history storage
# Format: {(user_id, channel_id): [message1, message2, ...]}
_conversation_history: Dict[tuple, List[Dict[str, Any]]] = {}
_max_history_per_conversation = 10  # Keep last 10 user-assistant exchanges
_history_ttl = 3600  # 1 hour TTL for conversations
_last_cleanup = time.time()

# Lazy initialization of OpenAI client to avoid errors if .env not loaded yet
_client = None
MODEL = os.getenv("MODEL_NAME", "gpt-4o")  # Use gpt-4o for function calling

def get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        _client = OpenAI(api_key=api_key)
    return _client

# Get router instance
router = get_router()

# Tracer configuration from environment variables
TRACER_ENABLE_CONSOLE = os.getenv("TRACER_ENABLE_CONSOLE", "true").lower() == "true"
TRACER_ENABLE_FILE = os.getenv("TRACER_ENABLE_FILE", "false").lower() == "true"
TRACER_LOG_FILE = os.getenv("TRACER_LOG_FILE", "function_trace.log")

# System prompt for the assistant
ASSISTANT_SYSTEM_PROMPT = f"""You are a helpful Slack assistant that can answer questions about the workspace using read-only tools.

{get_planning_prompt()}

When answering questions:
- Use tools to gather information before responding
- Provide clear, concise answers
- Include relevant details like channel names, user names, timestamps
- Timestamps are already formatted as human-readable dates (YYYY-MM-DD HH:MM:SS format)

**IMPORTANT - Tool Result Handling:**
- Check the tool result's "success" field first
- If success is true: Use the "data" field to answer the question. Do NOT say you're unable to retrieve data.
- If success is false: Check the "error.message" field and use that exact message to explain the issue to the user.
- Never say "I'm unable to retrieve" or "technical issue" unless the tool explicitly returns success: false with an error.

- For search results, summarize key findings and verify they're relevant to the query
- When search results are returned, check if they actually match what the user asked for
- If search results don't seem relevant, mention this to the user and suggest refining the query
- **IMPORTANT**: If search_messages fails with "not_allowed_token_type" or "missing_scope" (these errors 
  only occur with API mode, not JSON mode), this means the search API requires a user token. In this case, 
  offer to search specific channels instead using get_channel_history. For example: "I can't use the global 
  search, but I can search specific channels for you. Which channels should I check?" 
  NOTE: In JSON mode, search_messages should always work - if it fails, report the actual error message.
- **CRITICAL - Message Filtering**: When using get_channel_history to search for specific topics, you MUST 
  filter the messages to only include those that are actually relevant to the user's query. Do NOT return 
  all messages from a channel - only return messages that contain keywords or phrases related to what the 
  user asked for. If a channel has no relevant messages, say so clearly rather than returning unrelated messages.
- For message history, provide context and highlights
- For channel lists, list the channel names and brief details

**CONVERSATION CONTEXT:**
- You have access to previous messages in this conversation
- When a user asks a follow-up question, refer back to previous context
- If a user mentions something from earlier (like "that thread", "the cornering thread", or "what we discussed"), 
  use the conversation history to understand what they're referring to
- Maintain context across multiple questions in the same conversation
- If a user asks about something mentioned earlier, you don't need to ask them to repeat details

Always be helpful and respect user privacy.
"""


def execute_tool_call(tool_call, user_id: str, channel_id: Optional[str] = None, tracer=None) -> Dict[str, Any]:
    """
    Execute a tool call from GPT-4o.
    
    Args:
        tool_call: Tool call object from GPT-4o (ChatCompletionMessageFunctionToolCall)
        user_id: Slack user ID making the request
        channel_id: Channel ID where the request came from
        tracer: Optional FunctionCallTracer instance for tracing
    
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
    start_time = time.time()
    result = router.execute_tool(
        tool_name=tool_name,
        params=arguments,
        user_id=user_id,
        channel_id=channel_id
    )
    duration_ms = (time.time() - start_time) * 1000
    
    # Log function result to tracer
    if tracer:
        tracer.log_function_result(
            tool_name=tool_name,
            success=result.get("success", False),
            result_data=result if result.get("success") else None,
            error=result.get("error") if not result.get("success") else None,
            duration_ms=duration_ms
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


def _get_conversation_key(user_id: str, channel_id: Optional[str]) -> tuple:
    """Generate a unique key for conversation history."""
    return (user_id, channel_id or "dm")


def _get_conversation_history(user_id: str, channel_id: Optional[str]) -> List[Dict[str, Any]]:
    """Get conversation history for a user/channel."""
    key = _get_conversation_key(user_id, channel_id)
    return _conversation_history.get(key, [])


def _cleanup_old_conversations() -> None:
    """Remove conversations older than TTL."""
    global _conversation_history
    try:
        current_time = time.time()
        keys_to_remove = []
        
        for key, messages in _conversation_history.items():
            if messages:
                last_timestamp = messages[-1].get("timestamp", 0)
                if current_time - last_timestamp > _history_ttl:
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del _conversation_history[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old conversations")
    except Exception as e:
        logger.warning(f"Error during conversation cleanup: {e}")


def _add_to_conversation_history(
    user_id: str,
    channel_id: Optional[str],
    user_message: str,
    assistant_response: str
) -> None:
    """Add a user-assistant exchange to conversation history."""
    global _last_cleanup
    key = _get_conversation_key(user_id, channel_id)
    
    if key not in _conversation_history:
        _conversation_history[key] = []
    
    # Add user message and assistant response
    _conversation_history[key].append({
        "role": "user",
        "content": user_message,
        "timestamp": time.time()
    })
    _conversation_history[key].append({
        "role": "assistant",
        "content": assistant_response,
        "timestamp": time.time()
    })
    
    # Trim to max history
    if len(_conversation_history[key]) > _max_history_per_conversation * 2:
        _conversation_history[key] = _conversation_history[key][-_max_history_per_conversation * 2:]
    
    # Clean up old conversations periodically
    current_time = time.time()
    if current_time - _last_cleanup > 300:  # Every 5 minutes
        _cleanup_old_conversations()
        _last_cleanup = current_time


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
        # Initialize tracer for this session (create new instance per session)
        from .tools.tracer import FunctionCallTracer
        tracer = FunctionCallTracer(
            enable_console=TRACER_ENABLE_CONSOLE,
            enable_file=TRACER_ENABLE_FILE,
            log_file=TRACER_LOG_FILE
        )
        session_start_time = time.time()
        
        # Log tracer status for debugging
        if TRACER_ENABLE_CONSOLE:
            logger.info(f"[TRACER] Function call tracing enabled (console output)")
        else:
            logger.info(f"[TRACER] Function call tracing disabled (console output)")
        
        # Start tracing session
        tracer.start_session(user_query, user_id, channel_id)
        
        # Get conversation history (graceful degradation if it fails)
        try:
            history = _get_conversation_history(user_id, channel_id)
        except Exception as e:
            logger.warning(f"Failed to retrieve conversation history: {e}")
            history = []
        
        # Build messages list with system prompt, history, and current query
        messages = [
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}
        ]
        
        # Add conversation history (only user/assistant messages, not tool calls)
        for msg in history:
            # Only include user and assistant messages, skip tool calls
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current user query
        messages.append({"role": "user", "content": user_query})
        
        tool_calls_count = 0
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Log iteration start
            tracer.log_iteration_start(iteration, max_iterations)
            
            # Call GPT-4o
            response = get_openai_client().chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto"  # Let model decide when to use tools
            )
            
            message = response.choices[0].message
            
            # Log model response
            tracer.log_model_response(
                content=message.content,
                tool_calls=message.tool_calls
            )
            
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
                
                # Execute all tool calls (tracer will log them via execute_tool_call)
                for idx, tool_call in enumerate(message.tool_calls):
                    # Log function call before execution
                    tracer.log_function_call(
                        tool_name=tool_call.function.name,
                        arguments=tool_call.function.arguments,
                        tool_call_id=tool_call.id,
                        call_index=idx + 1,
                        total_calls=len(message.tool_calls)
                    )
                    
                    tool_result = execute_tool_call(tool_call, user_id, channel_id, tracer=tracer)
                    messages.append(tool_result)
                
                # Continue loop to get model's response to tool results
                continue
            else:
                # Model has finished (no more tool calls, has final answer)
                final_text = message.content or "I'm sorry, I couldn't generate a response."
                
                # Log final answer
                total_duration = time.time() - session_start_time
                tracer.log_final_answer(final_text, tool_calls_count, total_duration)
                
                # Save to conversation history
                try:
                    _add_to_conversation_history(user_id, channel_id, user_query, final_text)
                except Exception as e:
                    logger.warning(f"Failed to save conversation history: {e}")
                
                return {
                    "text": final_text,
                    "tool_calls": tool_calls_count,
                    "success": True,
                    "error": None
                }
        
        # Max iterations reached
        error_text = "I'm sorry, I reached the maximum number of tool calls. Please try rephrasing your question."
        if tracer:
            total_duration = time.time() - session_start_time
            tracer.log_final_answer(error_text, tool_calls_count, total_duration)
        return {
            "text": error_text,
            "tool_calls": tool_calls_count,
            "success": False,
            "error": "max_iterations_reached"
        }
    
    except Exception as e:
        logger.error(f"Error handling user query: {e}", exc_info=True)
        error_text = f"I encountered an error: {str(e)}. Please try again."
        # Try to log error if tracer exists
        try:
            if 'tracer' in locals() and tracer:
                tracer.log_final_answer(error_text, 0, None)
        except:
            pass
        return {
            "text": error_text,
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
        app = _get_bolt_app()
        if app:
            auth_result = app.get_openai_client().auth_test()
            if auth_result and isinstance(auth_result, dict):
                bot_user_id = auth_result.get("user_id")
                if bot_user_id:
                    text = text.replace(f"<@{bot_user_id}>", "").strip()
        # Also remove any other mentions that might be in the text
        import re
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    except Exception as e:
        logger.warning(f"Error getting bot user ID: {e}")
        # Fallback: just remove all mentions
        import re
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
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

