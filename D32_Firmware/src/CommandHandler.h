#ifndef CommandHandler_h
#define CommandHandler_h

#include <Arduino.h>

class CommandHandler {
public:
    CommandHandler();
    
    bool readCommand();
    const char* getCommand() { return _cmdBuffer; }
    bool is(const char* cmd);
    bool startsWith(const char* prefix);
    int getIntParam();
    long getLongParam();
    
    void displayHelp();

private:
    static const int CMD_BUFFER_SIZE = 64;
    char _cmdBuffer[CMD_BUFFER_SIZE];
    
    int findSpace();
};

#endif
