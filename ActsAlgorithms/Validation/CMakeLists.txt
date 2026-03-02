add_library(Validation SHARED)

# ----------------------------------------
# Sources
# ----------------------------------------
target_sources(Validation
    PRIVATE
    src/ResPlotTool.cpp
    src/RootTrackFitterPerformanceWriter.cpp
    src/RootTrackFinderPerformanceWriter.cpp
    # add more .cpp files here
)

# ----------------------------------------
# Include directories
# ----------------------------------------
target_include_directories(Validation
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
#        $<INSTALL_INTERFACE:include>
)

<<<<<<< Updated upstream
=======
# ----------------------------------------
# Compile definitions
# ----------------------------------------
# Uncomment the line below to enable edge holes in track summary
# target_compile_definitions(Validation PRIVATE ACTS_INCLUDE_EDGEHOLES)
>>>>>>> Stashed changes

find_library(ACTS_EXAMPLES_FRAMEWORK
    NAMES ActsExamplesFramework
    HINTS ${CMAKE_PREFIX_PATH}
    PATH_SUFFIXES lib lib64
    REQUIRED
)

#link_directories(${CMAKE_PREFIX_PATH}/lib64)

# ----------------------------------------
# Link against Acts and ExampleAlgorithms
# ----------------------------------------
target_link_libraries(Validation
    PUBLIC
    Acts::Core
    Acts::PluginRoot
    ${ACTS_EXAMPLES_FRAMEWORK}
    ExampleAlgorithms
  )
