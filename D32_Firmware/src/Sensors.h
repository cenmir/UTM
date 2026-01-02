#ifndef Sensors_h
#define Sensors_h

#include "Arduino.h" 
#include <Wire.h>
#include <AS5600.h>

#define TCAADDR 0x70

class Sensors {
  public:
    Sensors();
    void init(int);
    float readAngle(int);
    void posAndSpeed(int);
    int32_t readTotalPosition(int);
    float readAngularSpeed(int);
    
  private:
    AS5600 as5600;
    void tcaselect(uint8_t);
    double amsOffsets[2] = {0.0, 0.0};
};

#endif
