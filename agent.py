from livekit.agents import Agent
from prompts.system_prompt import JARVIS_INSTRUCTIONS
from tools.date_time import get_date_time
from tools.realtime_information import get_realtime_information
from tools.DesktopAutomation.apps import (
    open_application, 
    close_application, 
    switch_to_application, 
    rescan_installed_apps,
    manage_window_state,
)
from tools.DesktopAutomation.input_control import (
    type_text, 
    type_text_unicode, 
    press_key
)    

from tools.DesktopAutomation.ui_element_control import (
    click_ui_element,
    set_input_field_text,
    read_active_window_elements,
)

from tools.DesktopAutomation.browser_automation import (
    youtube_search_and_play,
    youtube_media_control,
    web_navigate,
    web_click_element,
    web_fill_form,
    read_web_page_content,
    take_page_screenshot,
    extract_page_links,
    web_scroll_page,
    web_select_dropdown_option,
    close_browser_tab,
    open_new_tab,
    switch_browser_tab,
    list_browser_tabs,
    web_go_back,
    web_go_forward,
    web_reload_page,
    youtube_account_action, 
)

from tools.DesktopAutomation.system_control import (
    set_system_volume,
    change_system_volume,
    mute_system_volume,
    get_system_volume,
    set_screen_brightness,
    change_screen_brightness,
    turn_off_display,
    lock_workstation,
    sleep_computer,
    shutdown_or_restart_pc,
    cancel_pc_shutdown,
    system_media_control,
    get_hardware_metrics,
)

from tools.music_tools import play_music_in_ui, control_music_player

class Jarvis(Agent):

    def __init__(self) -> None:
        super().__init__(
            instructions=JARVIS_INSTRUCTIONS,
            tools=[
                get_date_time,
                get_realtime_information,
                open_application,
                close_application,
                switch_to_application,
                rescan_installed_apps,
                manage_window_state,
                type_text, 
                type_text_unicode, 
                press_key,
                click_ui_element,
                set_input_field_text,
                read_active_window_elements,
                youtube_search_and_play,
                youtube_media_control,
                web_navigate,
                web_click_element,
                web_fill_form,
                read_web_page_content,
                take_page_screenshot,
                extract_page_links,
                web_scroll_page,
                web_select_dropdown_option,
                close_browser_tab,
                open_new_tab,
                switch_browser_tab,
                list_browser_tabs,
                web_go_back,
                web_go_forward,
                web_reload_page,
                youtube_account_action,
                set_system_volume,
                change_system_volume,
                mute_system_volume,
                get_system_volume,
                set_screen_brightness,
                change_screen_brightness,
                turn_off_display,
                lock_workstation,
                sleep_computer,
                shutdown_or_restart_pc,
                cancel_pc_shutdown,
                system_media_control,
                get_hardware_metrics,
                play_music_in_ui,
                control_music_player,
            ]
        )