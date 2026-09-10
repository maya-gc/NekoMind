# NekoMind Firmware - Projeto ESP-IDF; alvo pendente de escolha de placa
# Requer ESP-IDF >= 5.1 (validacao deste MVP ainda pendente)
cmake_minimum_required(VERSION 3.16)

set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(nekomind_firmware)
