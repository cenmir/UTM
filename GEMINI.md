# Gemini Project: Universal Testing Machine

This project is a custom-built Universal Testing Machine (UTM) used for tensile testing of materials. It is used for teaching and research at Jönköping University.

**Note:** This project is in the process of being converted from MATLAB to Python using PyQt6. The `App.m` file is retained for reference during this conversion.

## Project Overview

The project consists of three main parts:

*   **Hardware:** A physical testing machine with Nema 23 stepper motors, a load cell (HX711), and AS5600 magnetic encoders for position/speed feedback. It utilizes an I2C multiplexer.
*   **Firmware:** An Arduino-based firmware (`D32_Firmware/D32_Firmware.ino`) that controls the motors and sensors. It communicates with the host computer via a serial connection, accepting commands for motor control (up, down, stop, set speed, incremental moves) and data requests (load, angle, velocity). It uses `MobaTools` for stepper control and Rob Tillaart's libraries for HX711 and AS5600.
*   **Software:** A MATLAB application (`App.m` / `UTM.mlapp`) built with MATLAB App Designer that provides a graphical user interface (GUI) to:
    *   Control the UTM via serial communication with the Arduino firmware.
    *   Acquire and process data from the load cell and encoders.
    *   Visualize load and stress-strain curves in real-time.
    *   Save collected data (timestamp, raw force, calibrated force, position, strain, stress) to `.mat` files.
    *   Perform load cell calibration.
    *   Includes functionality for camera integration, potentially for Digital Image Correlation (DIC) using `vision.PointTracker` and `vision.BlobAnalysis` to track movement or features.
    A separate MATLAB script (`Software/data/process.m`) is used to post-process the collected `.mat` data files and generate stress-strain curves in an Excel file.

## Building and Running

### Firmware

The firmware is written for an Arduino-compatible board. To build and upload the firmware:

1.  Open `D32_Firmware/D32_Firmware.ino` in the Arduino IDE.
2.  Install the required libraries:
    *   `HX711` by Rob Tillaart
    *   `MobaTools`
    *   `AS5600` by Rob Tillaart
3.  Select the correct board and port.
4.  Upload the firmware.

### Software

The software is a MATLAB application. To run the application:

1.  Open MATLAB.
2.  Navigate to the project root directory.
3.  Run the `App.m` file (or open `UTM.mlapp` directly in App Designer).

To process the data:

1.  Ensure the `.mat` files are in the `Software/data` directory (or a specified data directory).
2.  Run the `Software/data/process.m` script from MATLAB.

## Development Conventions

*   The firmware communicates with the software using a simple serial protocol. Commands are sent as strings, and data is sent back as plain text.
*   The MATLAB application is built using the MATLAB App Designer, with code organized into properties for UI components and methods for logic (`startupFcn`, `GetSerialData`, `ProcessLoadData`, etc.).
*   Data is stored in `.mat` files, which are then processed by a separate MATLAB script (`Software/data/process.m`).
*   The output of the data post-processing is an Excel file with stress-strain curves.
*   The application includes features for camera control and image processing (Digital Image Correlation), suggesting an integrated approach to material testing.
*   Load cell calibration involves a two-point calibration using a known weight.