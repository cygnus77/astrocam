cmake_minimum_required(VERSION 3.10)
project(cam)
add_definitions(-DINDIGO_LINUX)

set(SOURCES
    app.c)

add_library(${PROJECT_NAME} SHARED ${SOURCES})
include_directories(${PROJECT_NAME} PUBLIC "/usr/include/indigo")
target_link_libraries(${PROJECT_NAME} "indigo")

add_executable(${PROJECT_NAME}dbg ${SOURCES})
include_directories(${PROJECT_NAME}dbg PUBLIC "/usr/include/indigo")
target_link_libraries(${PROJECT_NAME}dbg "indigo")

