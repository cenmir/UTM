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
    double getAngle(int);
    
  private:
    AS5600 ams5600;
    void tcaselect(uint8_t);
    double amsOffsets[2] = {0.0, 0.0};
};

#endif