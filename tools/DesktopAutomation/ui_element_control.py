import asyncio
import logging
from typing import Optional
import uiautomation as auto
from livekit.agents import function_tool, RunContext, ToolError

from .desktop_state import get_last_opened
from .apps import _force_foreground_window, _is_window_cloaked

logger = logging.getLogger("desktop_automation.ui")


def _get_target_window_control():
    """নিরাপদে অ্যাক্টিভ উইন্ডোর UI Automation কন্ট্রোল বের করে (COMError প্রটেক্টেড)।"""
    last = get_last_opened()
    if last and last.hwnd:
        try:
            import win32gui
            if win32gui.IsWindow(last.hwnd) and not _is_window_cloaked(last.hwnd):
                _force_foreground_window(last.hwnd)
                win = auto.ControlFromHandle(last.hwnd)
                if win and win.Exists(0, 0):
                    return win
        except Exception:
            pass

    try:
        fg = auto.GetForegroundControl()
        if fg and fg.Exists(0, 0):
            return fg
    except Exception:
        pass

    return None


@function_tool(
    name="click_ui_element",
    description=(
        "Click a specific visible UI element (Button, MenuItem, TabItem, Dialog option) by its visible label. "
        "Examples: 'Save', 'Don't Save', 'Cancel', 'File', 'OK', 'Close'."
    )
)
async def click_ui_element(
    context: RunContext,
    element_name: str,
    control_type: Optional[str] = None
) -> str:
    win = _get_target_window_control()
    if not win:
        raise ToolError("Active window detect nahi ho saka.")

    clean_name = element_name.strip()
    logger.info(f"Searching for UI Element '{clean_name}' in active window")

    target = None
    try:
        target = win.Control(Name=clean_name, searchDepth=8)
        if not target.Exists(maxSearchSeconds=1.2):
            for ctrl, _ in auto.WalkControl(win, maxDepth=8):
                if ctrl.Name and clean_name.lower() in ctrl.Name.lower():
                    target = ctrl
                    break
    except Exception as e:
        logger.warning(f"Error while walking control tree: {e}")

    if not target or not target.Exists(0, 0):
        raise ToolError(f"Active window mein '{clean_name}' element nahi mila.")

    clicked_successfully = False

    # ১. InvokePattern দিয়ে নেটিভ ক্লিক
    try:
        invoke_pattern = target.GetInvokePattern()
        if invoke_pattern:
            invoke_pattern.Invoke()
            clicked_successfully = True
    except Exception:
        pass

    # ২. TogglePattern (Checkbox/Toggle বাটন)
    if not clicked_successfully:
        try:
            toggle_pattern = target.GetTogglePattern()
            if toggle_pattern:
                toggle_pattern.Toggle()
                clicked_successfully = True
        except Exception:
            pass

    # ৩. Direct Native Click & Coordinate Fallback
    if not clicked_successfully:
        try:
            target.Click(simulateMove=False)
            clicked_successfully = True
        except Exception as ex:
            err_str = str(ex)
            # উইন্ডো বন্ধ হয়ে যাওয়ার কারণে -2147220991 এরর আসলে ক্লিক সফল হিসেবে গণ্য হবে
            if "-2147220991" in err_str or not target.Exists(0, 0):
                clicked_successfully = True
            else:
                # মাউস কোঅর্ডিনেট ফলব্যাক
                try:
                    rect = target.BoundingRectangle
                    if rect and (rect.right > rect.left) and (rect.bottom > rect.top):
                        cx = (rect.left + rect.right) // 2
                        cy = (rect.top + rect.bottom) // 2
                        import pyautogui
                        pyautogui.click(cx, cy)
                        clicked_successfully = True
                except Exception:
                    pass

    if clicked_successfully:
        return f"Boss, '{clean_name}' par click ho gaya hai."

    raise ToolError(f"'{clean_name}' element par click perform nahi kiya ja saka.")


@function_tool(
    name="set_input_field_text",
    description="Set text directly into an input field or text box in the active application."
)
async def set_input_field_text(
    context: RunContext,
    text: str,
    field_name: Optional[str] = None
) -> str:
    win = _get_target_window_control()
    if not win:
        raise ToolError("Active window detect nahi ho saka.")

    target = None
    try:
        if field_name:
            target = win.EditControl(Name=field_name, searchDepth=8)
            if not target.Exists(maxSearchSeconds=1.0):
                target = win.Control(Name=field_name, searchDepth=8)
        else:
            target = win.EditControl(searchDepth=8)
    except Exception:
        pass

    if not target or not target.Exists(0, 0):
        raise ToolError("Text enter karne ke liye koi input field nahi mila.")

    try:
        val_pattern = target.GetValuePattern()
        if val_pattern:
            val_pattern.SetValue(text)
            return f"Boss, input field mein '{text}' set kar diya gaya hai."
    except Exception:
        pass

    try:
        target.Click(simulateMove=False)
        await asyncio.sleep(0.1)
        target.SendKeys(text)
        return f"Boss, input field mein '{text}' type kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Field mein text set nahi ho saka: {e}")


@function_tool(
    name="read_active_window_elements",
    description="Inspect and read visible text, buttons, and dialog messages from the foreground window."
)
async def read_active_window_elements(context: RunContext) -> str:
    win = _get_target_window_control()
    if not win:
        return "Filhal screen par koi active window detect nahi ho raha hai."

    collected_labels = []
    try:
        for ctrl, _ in auto.WalkControl(win, maxDepth=6):
            try:
                if ctrl.Name and ctrl.Name.strip():
                    c_type = ctrl.ControlTypeName
                    name = ctrl.Name.strip()
                    if c_type in ["ButtonControl", "TextControl", "EditControl", "MenuItemControl", "TabItemControl"]:
                        collected_labels.append(f"[{c_type.replace('Control', '')}] {name}")
            except Exception:
                continue
    except Exception:
        return f"Window '{win.Name}' ke elements inspect karte waqt window close ho gayi."

    if not collected_labels:
        return f"Window '{win.Name}' mein koi visible interactive element nahi mila."

    summary = "\n".join(collected_labels[:25])
    return f"Active Window: {win.Name}\nVisible Elements:\n{summary}"