cmake_minimum_required(VERSION 3.20)
project(CrewBridge)

set(CMAKE_CXX_STANDARD 17)

add_executable(CrewBridge src/main.cpp)

target_include_directories(CrewBridge PRIVATE include)
target_link_directories(CrewBridge PRIVATE lib)
target_link_libraries(CrewBridge PRIVATE SimConnect.lib)
