"""
Agentic loop — LLM → tool calls → results → LLM (repeat).
"""
import re
import json
import logging

from llm.client import call_llm_with_tools
from llm.provider import resolve_provider
from agent.bridge import call_bridge
from agent.dispatch import dispatch_tool
from agent.tools import AGENT_TOOLS

logger = logging.getLogger(__name__)

# ── Response pattern detection ───────────────────────────────────────────────

_PLACEHOLDER_PATTERNS = re.compile(
    r"\bone moment\b|\blet me check\b|\blet me look\b|\bi'll check\b|"
    r"\bplease wait\b|\bfetching\b|\blooking up\b|\bchecking\b|\bstandby\b",
    re.IGNORECASE,
)

_GIVING_UP_PATTERNS = re.compile(
    r"not progressing|recommend refresh|try again later|cannot proceed|"
    r"having trouble|unable to proceed|seems to be stuck|doesn't seem|"
    r"not able to (click|proceed|continue|navigate)|struggling|refresh the page|"
    r"unfortunately.*cannot|i('m| am) unable|it seems.*form|the form.*not",
    re.IGNORECASE,
)

# ── Global stop flag (set via /api/agent/stop) ───────────────────────────────

_STOP_FLAG = False


def set_stop_flag(value: bool):
    global _STOP_FLAG
    _STOP_FLAG = value


# ── Browser tool names (used to decide whether to inject screenshots) ─────────

_BROWSER_TOOLS = {"view_healthhub", "interact_with_screen", "book_on_healthhub"}


# ── Main loop ────────────────────────────────────────────────────────────────

def run_agent(messages: list, patient_id: str, max_iter: int = 20) -> str:
    """
    Run the agentic loop: LLM → tool calls → results → LLM (repeat).
    Returns the final text response to show the user.
    """
    set_stop_flag(False)
    msgs = list(messages)
    last_text = ""
    tool_called_this_run = False
    scroll_retries = 0
    MAX_SCROLL_RETRIES = 4

    # Only inject screenshots if the browser has been used in this session
    browser_was_used = _browser_active_in_history(msgs)

    _inject_screenshot(msgs, force=False, browser_active=browser_was_used)

    for iteration in range(max_iter):
        if _STOP_FLAG:
            return "Execution stopped."

        resp = call_llm_with_tools(msgs, AGENT_TOOLS, max_tokens=1200)
        if resp is None:
            return last_text or "[AI service unavailable. Please check your API key.]"

        msg = resp.choices[0].message

        # ── Primary path: native tool_calls ──────────────────────────────────
        if msg.tool_calls:
            tool_called_this_run = True
            msgs.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                result = dispatch_tool(tc.function.name, tc.function.arguments, patient_id)
                result_str = json.dumps(result, ensure_ascii=False)
                # Truncate large tool results to prevent context overflow
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "... [truncated]"
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

                # Auto-scroll on element-not-found errors
                if _is_not_found_error(result) and scroll_retries < MAX_SCROLL_RETRIES:
                    scroll_retries += 1
                    call_bridge("/api/browser/action", {"action": "scroll", "distance": 600}, timeout=10)
                    msgs.append({"role": "user", "content": (
                        f"[SYSTEM – Auto-scroll #{scroll_retries}/{MAX_SCROLL_RETRIES}] "
                        "Element not found. I scrolled down to reveal more content. "
                        "Call read_page again to get the updated element list before retrying."
                    )})

            used_browser = any(tc.function.name in _BROWSER_TOOLS for tc in msg.tool_calls)
            if used_browser:
                browser_was_used = True
                _inject_screenshot(msgs, force=True, browser_active=True)
            continue

        # ── Fallback path: <tool_call>JSON</tool_call> in text ───────────────
        text = msg.content or ""
        last_text = text

        parsed = _extract_json_tool_call(text)
        if parsed:
            tool_called_this_run = True
            tool_name = parsed.get("tool") or parsed.get("name") or parsed.get("function", "")
            tool_args = parsed.get("params") or parsed.get("arguments") or parsed.get("args") or {}
            result = dispatch_tool(tool_name, tool_args, patient_id)
            result_str = json.dumps(result, ensure_ascii=False)
            clean_text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL).strip()
            if clean_text:
                msgs.append({"role": "assistant", "content": clean_text})
            msgs.append({"role": "user", "content": f"Tool result for {tool_name}: {result_str}"})
            if tool_name in _BROWSER_TOOLS:
                browser_was_used = True
                _inject_screenshot(msgs, force=True, browser_active=True)
            continue

        # ── Detect placeholder ("one moment / let me check") ─────────────────
        if not tool_called_this_run and _PLACEHOLDER_PATTERNS.search(text):
            msgs.append({"role": "assistant", "content": text})
            msgs.append({"role": "user", "content":
                         "Please call the appropriate tool now to get the actual information."})
            continue

        # ── Detect giving-up ("form isn't progressing / recommend refreshing") ─
        if browser_was_used and _GIVING_UP_PATTERNS.search(text):
            msgs.append({"role": "assistant", "content": text})
            msgs.append({"role": "user", "content": (
                "[SYSTEM] Do NOT give up. You are controlling a real browser. "
                "Step 1: Call interact_with_screen(action='clear_modals'). "
                "Step 2: Call interact_with_screen(action='read_page'). "
                "Step 3: Click any Yes/No/Continue/Confirm button using click_text with role=button: "
                "interact_with_screen(action='click_text', text='Yes', role='button') or "
                "interact_with_screen(action='click_text', text='No', role='button'). "
                "ALWAYS use click_text with role=button — NOT coordinate clicks — for form buttons. "
                "NEVER ask the user to do anything. Continue autonomously now."
            )})
            continue

        # ── No tool calls — final response ────────────────────────────────────
        return text

    return last_text or "I'm still navigating — please give me a moment and try again."


# ── Helpers ──────────────────────────────────────────────────────────────────

def _browser_active_in_history(msgs: list) -> bool:
    return any(
        m.get("role") == "assistant" and
        any(tc.get("function", {}).get("name", "") in _BROWSER_TOOLS
            for tc in (m.get("tool_calls") or []))
        for m in msgs
    )


def _inject_screenshot(msg_list: list, force: bool, browser_active: bool):
    """Append a screenshot message if the provider supports vision."""
    if not force and not browser_active:
        return
    provider = resolve_provider()
    if not provider or not provider.get("vision", True):
        return  # Skip for Groq / SEA-LION — they can't use images
    try:
        state = call_bridge("/api/browser/state", method="GET", timeout=5)
        if isinstance(state, dict) and state.get("image"):
            content = [
                {"type": "text", "text": "Screenshot of current HealthHub screen:"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{state['image']}"}},
            ]
            if state.get("on_singpass_page"):
                content.append({"type": "text", "text":
                    "[SYSTEM: Browser shows Singpass QR code. Guide the user to scan it with their Singpass app.]"})
            msg_list.append({"role": "user", "content": content})
    except Exception:
        pass


def _is_not_found_error(result) -> bool:
    err = result.get("error", "") if isinstance(result, dict) else ""
    return bool(err and any(x in err.lower() for x in
                            ["not found", "could not find", "no element", "no match",
                             "timed out", "unable to find"]))


def _extract_json_tool_call(text: str) -> dict | None:
    """Extract tool call JSON from <tool_call>{...}</tool_call> in model output."""
    match = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except Exception:
        return None
