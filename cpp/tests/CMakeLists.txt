# Test unit untuk pustaka inti (xaviq_core) memakai QtTest.
qt_add_executable(test_core test_core.cpp)
target_link_libraries(test_core PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_core COMMAND test_core)

# Test McpClient dengan mock server (QTcpServer). Butuh Qt6::Network.
qt_add_executable(test_mcp test_mcp.cpp)
target_link_libraries(test_mcp PRIVATE xaviq_core Qt6::Test Qt6::Core Qt6::Network)
add_test(NAME test_mcp COMMAND test_mcp)

# Test backend (model, util simbol, parser, McpBackend end-to-end via mock).
qt_add_executable(test_backend test_backend.cpp)
target_link_libraries(test_backend PRIVATE xaviq_core Qt6::Test Qt6::Core Qt6::Network)
add_test(NAME test_backend COMMAND test_backend)

# Test indikator (correctness vs referensi Python).
qt_add_executable(test_indicators test_indicators.cpp)
target_link_libraries(test_indicators PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_indicators COMMAND test_indicators)

# Test engine (strategi, TradeRules, BotEngine) dengan backend palsu.
qt_add_executable(test_engine test_engine.cpp)
target_link_libraries(test_engine PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_engine COMMAND test_engine)

# Test engine skrip (QJSEngine + ctx + sandbox).
qt_add_executable(test_script test_script.cpp)
target_link_libraries(test_script PRIVATE xaviq_core Qt6::Test Qt6::Core Qt6::Qml)
add_test(NAME test_script COMMAND test_script)

# Test controller + worker thread (integrasi, backend palsu).
qt_add_executable(test_controller test_controller.cpp)
target_link_libraries(test_controller PRIVATE xaviq_core Qt6::Test Qt6::Core Qt6::Qml)
add_test(NAME test_controller COMMAND test_controller)
