#include "Sensors.h"

Sensors::Sensors(void) {
  Wire.begin();
}

// Select the input of the I2C Multiplexer
void Sensors::tcaselect(uint8_t i) {
  if (i > 1) {
    Serial.print("Error: We only have 2 sensors, index ");
    Serial.print(i);
    Serial.println(" provided.");
    return;
  }

  Wire.beginTransmission(TCAADDR);
  Wire.write(1 << i);
  Wire.endTransmission();
}

void Sensors::init(int id) {
  Serial.print("Selecting id");
  Serial.println(id);
  tcaselect(id);
  Serial.print("Initializing AS5600 id:");
  Serial.println(id);

  // If magnet is not detected
  if (ams5600.detectMagnet() == 0) {
    while(1) {
      if (ams5600.detectMagnet() == 1){
        Serial.print("Current Magnitude: ");
        Serial.println(ams5600.readMagnitude());
        break;
      }
      else {
        Serial.println("Can not detect magnet");
        delay(1000);
      }
    }
  }
}

double Sensors::getAngle(int id) {
  tcaselect(id);
  double retVal = (ams5600.rawAngle() * AS5600_RAW_TO_DEGREES ) - amsOffsets[id];

  //if (retVal <= -180) retVal = 360+retVal;
  //if (retVal > 180) retVal = 360-retVal;

  return retVal;
}