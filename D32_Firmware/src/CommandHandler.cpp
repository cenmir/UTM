#include "CommandHandler.h"

CommandHandler::CommandHandler() {
    _cmdBuffer[0] = '\0';
}

bool CommandHandler::readCommand() {
    if (!Serial.available()) return false;
    
    int idx = 0;
    unsigned long startTime = millis();
    
    // Read until newline or buffer full
    while (idx < CMD_BUFFER_SIZE - 1) {
        if (Serial.available()) {
            char c = Serial.read();
            if (c == '\n' || c == '\r') {
                break;
            }
            _cmdBuffer[idx++] = c;
        }
        // Timeout after 100ms
        if (millis() - startTime > 100) break;
    }
    
    _cmdBuffer[idx] = '\0'; // Null terminate
    return idx > 0;
}

bool CommandHandler::is(const char* cmd) {
    return strcmp(_cmdBuffer, cmd) == 0;
}

bool CommandHandler::startsWith(const char* prefix) {
    return strncmp(_cmdBuffer, prefix, strlen(prefix)) == 0;
}

int CommandHandler::findSpace() {
    for (int i = 0; i < CMD_BUFFER_SIZE; i++) {
        if (_cmdBuffer[i] == ' ') return i;
        if (_cmdBuffer[i] == '\0') return -1;
    }
    return -1;
}

int CommandHandler::getIntParam() {
    int spaceIdx = findSpace();
    if (spaceIdx < 0) return 0;
    return atoi(&_cmdBuffer[spaceIdx + 1]);
}

long CommandHandler::getLongParam() {
    int spaceIdx = findSpace();
    if (spaceIdx < 0) return 0;
    return atol(&_cmdBuffer[spaceIdx + 1]);
}

void CommandHandler::displayHelp() {
    Serial.println("----------------------");
    Serial.println("Valid Commands are:");
    Serial.println("");
    Serial.println("'GetLoad'                           - Returns the latest load cell reading");
    Serial.println("'GetVelocity'                       - Returns the angular velocity of each sensor");
    Serial.println("'GetTotalAngle'                     - Returns the total change of the angle since start");
    Serial.println("'GetSteps'                          - Returns the total number of steps since start");
    Serial.println("'GetVersion'                        - Returns the firmware version number");
    Serial.println("'Enable' / 'Disable'                - Enables/Disables the motors");
    Serial.println("'Stop'                              - Slows the motors to a stop");
    Serial.println("'EStop'                             - Breaks the motors to a stop immediately");
    Serial.println("'SetSpeed' <RPM*10>                 - Sets the rotational speed to rpm times 10");
    Serial.println("'Up' / 'Down'                       - Moves the motors");
    Serial.println("'Start'                             - Start rotating the motors at 100 rpm forward");
    Serial.println("'LoadCellOn' / 'LoadCellOff'        - Continuous reading every 50ms");
    Serial.println("'SensorsOn' / 'SensorsOff'          - Continuous reading every 50ms");
    Serial.println("'MoveSteps' <steps>                 - Move a specific number of steps");
    Serial.println("'SetRampLength' <length>            - Set acceleration ramp length");
    Serial.println("----------------------");
}
