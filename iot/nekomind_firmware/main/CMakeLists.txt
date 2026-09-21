idf_component_register(
    SRCS
        "nekomind_main.c"
        "board_spi.c"
        "audio_transport.c"
        "board_touch.c"
        "display_ui.c"
        "avatar_state.c"
        "neko_controller.c"
        "neko_layout.c"
        "neko_protocol.c"
        "session_controller.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_timer driver esp_driver_usb_serial_jtag nvs_flash vfs
)
