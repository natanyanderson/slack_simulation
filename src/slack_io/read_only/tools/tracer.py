"""
Function call tracing for model decision tracking.
Provides detailed tracing of the model's thought/action process.
"""
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class TraceEventType(Enum):
    """Types of trace events."""
    USER_QUERY = "user_query"
    MODEL_RESPONSE = "model_response"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    ITERATION_START = "iteration_start"
    ITERATION_END = "iteration_end"
    FINAL_ANSWER = "final_answer"


class FunctionCallTracer:
    """
    Tracer for tracking model function calls and decision-making process.
    """
    
    def __init__(self, enable_console: bool = True, enable_file: bool = False, log_file: Optional[str] = None):
        """
        Initialize the tracer.
        
        Args:
            enable_console: Whether to print traces to console
            enable_file: Whether to write traces to file
            log_file: Path to log file (if enable_file is True)
        """
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.log_file = log_file or "function_trace.log"
        self.trace_session: List[Dict[str, Any]] = []
        self.current_iteration = 0
        self.session_start_time = None
        
    def start_session(self, user_query: str, user_id: str, channel_id: Optional[str] = None):
        """Start a new tracing session."""
        self.trace_session = []
        self.current_iteration = 0
        self.session_start_time = time.time()
        
        event = {
            "type": TraceEventType.USER_QUERY.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "user_query": user_query,
                "user_id": user_id,
                "channel_id": channel_id
            }
        }
        self._add_event(event)
        self._print_event(event)
        
    def log_iteration_start(self, iteration: int, max_iterations: int):
        """Log the start of an iteration."""
        self.current_iteration = iteration
        event = {
            "type": TraceEventType.ITERATION_START.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "iteration": iteration,
                "max_iterations": max_iterations
            }
        }
        self._add_event(event)
        self._print_event(event)
        
    def log_model_response(self, content: Optional[str], tool_calls: Optional[List] = None):
        """Log the model's response (before executing tool calls)."""
        event = {
            "type": TraceEventType.MODEL_RESPONSE.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "iteration": self.current_iteration,
                "content": content,
                "has_tool_calls": tool_calls is not None and len(tool_calls) > 0,
                "tool_call_count": len(tool_calls) if tool_calls else 0
            }
        }
        self._add_event(event)
        self._print_event(event)
        
        # If tool calls are present, log details
        if tool_calls:
            for i, tool_call in enumerate(tool_calls):
                self.log_function_call(
                    tool_name=tool_call.function.name if hasattr(tool_call, 'function') else tool_call.get('function', {}).get('name'),
                    arguments=tool_call.function.arguments if hasattr(tool_call, 'function') else tool_call.get('function', {}).get('arguments'),
                    tool_call_id=tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                    call_index=i + 1,
                    total_calls=len(tool_calls)
                )
    
    def log_function_call(
        self,
        tool_name: str,
        arguments: str,
        tool_call_id: Optional[str] = None,
        call_index: int = 1,
        total_calls: int = 1
    ):
        """Log a function call request."""
        try:
            args_dict = json.loads(arguments) if isinstance(arguments, str) else arguments
        except (json.JSONDecodeError, TypeError):
            args_dict = {"raw": str(arguments)}
        
        event = {
            "type": TraceEventType.FUNCTION_CALL.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "iteration": self.current_iteration,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "arguments": args_dict,
                "call_index": call_index,
                "total_calls": total_calls
            }
        }
        self._add_event(event)
        self._print_event(event)
        
    def log_function_result(
        self,
        tool_name: str,
        success: bool,
        result_data: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None
    ):
        """Log a function call result."""
        # Extract summary information
        summary = {}
        if success and result_data:
            data = result_data.get("data", {})
            if "channels" in data:
                summary["channels_returned"] = len(data.get("channels", []))
            elif "messages" in data:
                if isinstance(data["messages"], list):
                    summary["messages_returned"] = len(data["messages"])
                elif isinstance(data["messages"], dict) and "matches" in data["messages"]:
                    summary["search_matches"] = len(data["messages"].get("matches", []))
            elif "users" in data:
                summary["users_returned"] = len(data.get("users", []))
            elif "members" in data:
                summary["members_returned"] = len(data.get("members", []))
        elif not success and error:
            summary["error_type"] = error.get("type")
            summary["error_message"] = error.get("message")
        
        event = {
            "type": TraceEventType.FUNCTION_RESULT.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "iteration": self.current_iteration,
                "tool_name": tool_name,
                "success": success,
                "summary": summary,
                "duration_ms": duration_ms
            }
        }
        self._add_event(event)
        self._print_event(event)
        
    def log_final_answer(self, answer: str, total_tool_calls: int, total_duration: Optional[float] = None):
        """Log the final answer."""
        event = {
            "type": TraceEventType.FINAL_ANSWER.value,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "answer": answer,
                "total_tool_calls": total_tool_calls,
                "total_duration_seconds": total_duration,
                "iterations": self.current_iteration
            }
        }
        self._add_event(event)
        self._print_event(event)
        
        # Write session to file if enabled
        if self.enable_file:
            self._write_session_to_file()
    
    def _add_event(self, event: Dict[str, Any]):
        """Add an event to the trace session."""
        self.trace_session.append(event)
    
    def _print_event(self, event: Dict[str, Any]):
        """Print an event to console if enabled."""
        if not self.enable_console:
            return
            
        event_type = event["type"]
        data = event["data"]
        
        if event_type == TraceEventType.USER_QUERY.value:
            print(f"\n{'#'*80}")
            print(f"[TRACE] USER QUERY")
            print(f"{'#'*80}")
            print(f"Query: {data['user_query']}")
            print(f"User: {data['user_id']}, Channel: {data.get('channel_id', 'DM')}")
            print(f"{'#'*80}\n")
            
        elif event_type == TraceEventType.ITERATION_START.value:
            print(f"\n{'='*80}")
            print(f"[TRACE] ITERATION {data['iteration']}/{data['max_iterations']}")
            print(f"{'='*80}\n")
            
        elif event_type == TraceEventType.MODEL_RESPONSE.value:
            if data['has_tool_calls']:
                print(f"[TRACE] Model decided to call {data['tool_call_count']} function(s)")
            else:
                print(f"[TRACE] Model provided final answer (no function calls)")
                if data.get('content'):
                    preview = data['content'][:150] + "..." if len(data['content']) > 150 else data['content']
                    print(f"[TRACE] Answer preview: {preview}")
            
        elif event_type == TraceEventType.FUNCTION_CALL.value:
            print(f"\n{'─'*80}")
            print(f"[TRACE] FUNCTION CALL #{data['call_index']}/{data['total_calls']}: {data['tool_name']}")
            print(f"{'─'*80}")
            print(f"Arguments:")
            print(json.dumps(data['arguments'], indent=2))
            print(f"{'─'*80}\n")
            
        elif event_type == TraceEventType.FUNCTION_RESULT.value:
            status = "✅ SUCCESS" if data['success'] else "❌ FAILED"
            print(f"\n{'─'*80}")
            print(f"[TRACE] FUNCTION RESULT: {data['tool_name']} - {status}")
            print(f"{'─'*80}")
            if data['success']:
                summary = data.get('summary', {})
                if summary:
                    print("Summary:")
                    for key, value in summary.items():
                        print(f"  • {key}: {value}")
            else:
                summary = data.get('summary', {})
                if 'error_type' in summary:
                    print(f"Error Type: {summary['error_type']}")
                if 'error_message' in summary:
                    print(f"Error Message: {summary['error_message']}")
            if data.get('duration_ms'):
                print(f"Duration: {data['duration_ms']:.2f}ms")
            print(f"{'─'*80}\n")
            
        elif event_type == TraceEventType.FINAL_ANSWER.value:
            print(f"\n{'#'*80}")
            print(f"[TRACE] FINAL ANSWER")
            print(f"{'#'*80}")
            print(f"Answer: {data['answer'][:300]}..." if len(data['answer']) > 300 else f"Answer: {data['answer']}")
            print(f"\nSession Summary:")
            print(f"  • Total tool calls: {data['total_tool_calls']}")
            print(f"  • Iterations: {data['iterations']}")
            if data.get('total_duration_seconds'):
                print(f"  • Total duration: {data['total_duration_seconds']:.2f}s")
            print(f"{'#'*80}\n")
    
    def _write_session_to_file(self):
        """Write the entire trace session to a file."""
        if not self.trace_session:
            return
            
        try:
            session_data = {
                "session_start": self.session_start_time,
                "session_end": time.time(),
                "duration_seconds": time.time() - self.session_start_time if self.session_start_time else None,
                "events": self.trace_session
            }
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(session_data, indent=2) + "\n\n")
        except Exception as e:
            print(f"[TRACER] Error writing to log file: {e}")
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get a summary of the trace session."""
        function_calls = [e for e in self.trace_session if e["type"] == TraceEventType.FUNCTION_CALL.value]
        function_results = [e for e in self.trace_session if e["type"] == TraceEventType.FUNCTION_RESULT.value]
        
        return {
            "total_events": len(self.trace_session),
            "function_calls": len(function_calls),
            "iterations": self.current_iteration,
            "duration_seconds": time.time() - self.session_start_time if self.session_start_time else None,
            "tools_used": [e["data"]["tool_name"] for e in function_calls]
        }


# Global tracer instance (can be configured)
_global_tracer: Optional[FunctionCallTracer] = None


def get_tracer(enable_console: bool = True, enable_file: bool = False, log_file: Optional[str] = None) -> FunctionCallTracer:
    """
    Get the global tracer instance.
    
    Args:
        enable_console: Whether to print traces to console
        enable_file: Whether to write traces to file
        log_file: Path to log file
    """
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = FunctionCallTracer(
            enable_console=enable_console,
            enable_file=enable_file,
            log_file=log_file
        )
    return _global_tracer


def reset_tracer():
    """Reset the global tracer (useful for testing)."""
    global _global_tracer
    _global_tracer = None

