# Test unit untuk pustaka inti (xaviq_core) memakai QtTest.
qt_add_executable(test_core test_core.cpp)
target_link_libraries(test_core PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_core COMMAND test_core)

# Test indikator visual (correctness vs referensi matematis).
qt_add_executable(test_indicators test_indicators.cpp)
target_link_libraries(test_indicators PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_indicators COMMAND test_indicators)

# Test PyBridge worker (integrasi Python IPC bridge via stdio NDJSON).
qt_add_executable(test_pybridge test_pybridge.cpp)
target_link_libraries(test_pybridge PRIVATE xaviq_core Qt6::Test Qt6::Core)
add_test(NAME test_pybridge COMMAND test_pybridge)

# Test controller QML bridge + UI integration.
qt_add_executable(test_controller test_controller.cpp)
target_link_libraries(test_controller PRIVATE xaviq_core Qt6::Test Qt6::Core Qt6::Qml)
add_test(NAME test_controller COMMAND test_controller)
