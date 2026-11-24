cmake_minimum_required(VERSION 3.21)

project(XaviqTradingEngine VERSION 3.2.4 LANGUAGES CXX)

# Resource Windows (ikon EXE). MinGW mengompilasi .rc via windres.
if(WIN32)
    enable_language(RC)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# Qt 6 (kit MinGW). CMAKE_PREFIX_PATH diarahkan ke C:/Qt/6.8.1/mingw_64 lewat env.ps1.
# CATATAN: build HARUS dari path tanpa spasi (junction C:\XaviqCpp) karena
# qmlimportscanner Qt gagal bila path mengandung spasi (mis. "Bot Trading").
find_package(Qt6 REQUIRED COMPONENTS Core Qml Quick QuickControls2 Network Test)

qt_standard_project_setup()

# ----- Pustaka inti (backend-agnostik, tanpa GUI langsung) -----
# Mengelola settings, logging, indikator visual chart, serta IPC bridge ke backend Python.
add_library(xaviq_core STATIC
    src/core/Logger.cpp
    src/core/Settings.cpp
    src/core/ConfigStore.cpp
    src/core/SecureStore.cpp
    src/indicators/Indicators.cpp
    src/app/PyBridgeWorker.cpp
    src/app/UpdateManager.cpp
    src/app/BotController.cpp
)
target_include_directories(xaviq_core PUBLIC src)
target_link_libraries(xaviq_core PUBLIC Qt6::Core Qt6::Network Qt6::Qml)

qt_add_executable(xaviq
    src/main.cpp
    src/ui/JsHighlighter.cpp
    resources.qrc
    $<$<BOOL:${WIN32}>:app.rc>
)

target_link_libraries(xaviq PRIVATE
    xaviq_core
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Network
)

# Aplikasi GUI (tanpa console window) di Windows.
set_target_properties(xaviq PROPERTIES WIN32_EXECUTABLE ON)

# ----- Testing -----
enable_testing()
add_subdirectory(tests)
