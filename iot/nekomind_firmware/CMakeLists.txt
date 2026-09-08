# NekoMind Firmware - Projeto ESP-IDF para ESP32-S3
# Requer ESP-IDF >= 5.1 (testado com v5.3.x)
cmake_minimum_required(VERSION 3.16)

set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(nekomind_firmware)
