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
  if (as5600.detectMagnet() == 0) {
    while(1) {
      if (as5600.detectMagnet() == 1){
        Serial.print("Current Magnitude: ");
        Serial.println(as5600.readMagnitude());
        break;
      }
      else {
        Serial.println("Can not detect magnet");
        delay(1000);
      }
    }
  }
}

float Sensors::readAngle(int id) {
  // degrees per second
  tcaselect(id);
  return as5600.readAngle() * AS5600_RAW_TO_DEGREES;
}

void Sensors::posAndSpeed(int id){
  tcaselect(id);
  as5600.readAngle();
  Serial.print(as5600.getCumulativePosition(false));
  Serial.print("\t");
  Serial.println(as5600.getAngularSpeed(AS5600_MODE_DEGREES, false));
}

int32_t Sensors::readTotalPosition(int id){
  tcaselect(id);
  as5600.readAngle();

  return as5600.getCumulativePosition(false);

}

float Sensors::readAngularSpeed(int id){
  tcaselect(id);
  as5600.readAngle();

  return as5600.getAngularSpeed(AS5600_MODE_DEGREES, false);

}

