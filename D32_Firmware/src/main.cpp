#include <Arduino.h>
#include <HX711.h> // https://github.com/RobTillaart/HX711

#include <Wire.h>
#include <MobaTools.h>
#include "Sensors.h"
#include "CommandHandler.h"

// Define LED_BUILTIN for ESP32 if not already defined
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

// ============================================
// FIRMWARE VERSION - UPDATE ON EVERY UPLOAD!
// ============================================
const char* FIRMWARE_VERSION = "1.2.0";



#define DATA_PIN    16     // HX711
#define CLOCK_PIN   4      // HX711
#define STEP_PIN   14      // Stepper driver step pin
#define DIR_PIN    27      // Stepper driver direction  pin
#define ENABLE_PIN 26      // Stepper driver enable pin

const int SPEED_SWITCH_PIN = 2; // HIGH is slow 
const int UP_BUTTON_PIN    = 17;
const int DOWN_BUTTON_PIN  = 15;

#define TCAADDR 0x70 // I2C multiplexer adress
#define SENS_IDX 0   // Which sensor to read
#define NUMBER_READINGS 20 // For averaging the speed

bool readLoadCell = false;
bool readSensors = false;
bool readAngle = false;
bool readAngularSpeed = false;

int32_t totalPosition = 0;
float   angularSpeed  = 0;
float angularSpeedBuffer[NUMBER_READINGS];    // Circular buffer for storing readings
int bufferIndex = 0;               // Index to track the position in the buffer
float averageAngularSpeed;      // Averaged angular speed values
long force = 0;

bool speedSwitchState = HIGH; // HIGH is slow and default

HX711 LoadCell;

Sensors sensors; // Rotation sensors

const int STEPS_REVOLUTION = 200*8;
MoToStepper stepper( STEPS_REVOLUTION, STEPDIR ); // Mode is stepdir

// MoToButtons setup for simplified button handling
const byte buttonPins[] = {UP_BUTTON_PIN, DOWN_BUTTON_PIN};
MoToButtons buttons(buttonPins, 2, 20, 500); // 2 buttons, 20ms debounce, 500ms for long press
enum { UP_BTN = 0, DOWN_BTN = 1 }; // Button indices

// Command handler for serial communication
CommandHandler* cmdHandler = nullptr;

// Function declarations
void ProcessSensors();
void ReportLoadCell();
float Average(float buffer[]);
void CheckButtonStates();
void MoveUp();
void MoveDown();
void Stop();
void StartUp();
void ScanI2C();
void ProcessSerialCommands();

void setup() {
  Wire.begin();
  Serial.begin(9600);
  while (!Serial);

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(SPEED_SWITCH_PIN, INPUT_PULLUP);

  LoadCell.begin(DATA_PIN, CLOCK_PIN, true);
  // Loadcell calibration is done in external software
  //LoadCell.set_offset(4294935301);
  //LoadCell.set_scale(57.144153594970703);

  StartUp();

  // Initialize all sensors
  sensors = Sensors();
  for (int i = 0; i < 1; i++) {
    sensors.init(i);
  }

  // =======================================
  // Stepper config
  // =======================================
  stepper.attach(STEP_PIN, DIR_PIN);

  //stepper.attachEnable(ENABLE_PIN, 10, HIGH);
  // if you want to switch off power when stepper reached position
  
  stepper.setRampLen(100);
  // Ramp length in steps. The permissible ramp length depends on the step rate, and a
  // maximum of 16000 for high step rates. For step rates below 2steps/sec, ramping is no
  // longer possible. If ramplen is outside the permissible range, the value is adjusted.

  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);
  
  // Initialize command handler
  cmdHandler = new CommandHandler();
  
  cmdHandler->displayHelp();
}

void loop() {
  ProcessSerialCommands();
  CheckButtonStates();

  // Only read data when it is already available.
  if (LoadCell.is_ready()) {
    force = LoadCell.read();
    ReportLoadCell();
  }

  ProcessSensors();
}

void ProcessSensors(){
  static uint32_t delayTimeSensors;
  if ( millis() - delayTimeSensors >= 50 ) {
    delayTimeSensors = millis();
    //sensors.posAndSpeed(0);
    totalPosition = sensors.readTotalPosition(SENS_IDX);

    angularSpeed = sensors.readAngularSpeed(SENS_IDX) / 6; // rpm

    // Add new readings to the circular buffer
    angularSpeedBuffer[bufferIndex] = angularSpeed;

    // Increment the buffer index (wrap around using modulo)
    bufferIndex = (bufferIndex + 1) % NUMBER_READINGS;

    // Calculate the average of the last N readings
    averageAngularSpeed = Average(angularSpeedBuffer);

    if (readSensors) {
      Serial.print(totalPosition); Serial.print("\t");
      Serial.print(angularSpeed); Serial.print("\t");
      Serial.print(averageAngularSpeed); Serial.print("\n");
    }
  }

  
}

void ReportLoadCell(){
  static uint32_t delayTimeLoadCell = 0;
  if (readLoadCell){
    if ( millis() - delayTimeLoadCell >= 50 ) { // Max 20Hz, loadcell should report at 10Hz
      delayTimeLoadCell = millis();
      Serial.print(force); Serial.print("\n");
    }  
  }
}


// Function to calculate the average of the values in a circular buffer
float Average(float buffer[]) {
  float sum = 0.0;
  for (int i = 0; i < NUMBER_READINGS; i++) {
    sum += buffer[i];
  }
  return sum / NUMBER_READINGS;
}


void CheckButtonStates(){
  buttons.processButtons(); // Process button states with debouncing
  
  speedSwitchState = digitalRead(SPEED_SWITCH_PIN);
  
  // UP button - start moving when pressed, stop when released
  if (buttons.pressed(UP_BTN)) {
    MoveUp();
  }
  if (buttons.released(UP_BTN)) {
    Stop();
  }
  
  // DOWN button - start moving when pressed, stop when released
  if (buttons.pressed(DOWN_BTN)) {
    MoveDown();
  }
  if (buttons.released(DOWN_BTN)) {
    Stop();
  }
}

void MoveUp(){
  digitalWrite(ENABLE_PIN, HIGH);
  if (speedSwitchState == LOW){
    Serial.println("Going up fast!");
    stepper.setSpeed(5000);
  } else{
    Serial.println("Going up!");
    stepper.setSpeed(500);
  }
  
  stepper.rotate(-1);
  
}

void MoveDown(){
  digitalWrite(ENABLE_PIN, HIGH);
  if (speedSwitchState == LOW){
    Serial.println("Going down fast!");
    stepper.setSpeed(5000);
  } else{
    Serial.println("Going down!");
    stepper.setSpeed(500);
  }

  stepper.rotate(1);
}

void Stop(){
  Serial.println("Stop and halt!");

  stepper.rotate(0);
}

void StartUp(){

  for (int i=0; i<5; i++){
    delay(500);
    digitalWrite(LED_BUILTIN, HIGH);  
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
  }

  Serial.println("\n\n\n\n");
  Serial.println("=====================================================");
  Serial.println("Welcome to Mirzas Universal Testing Machine Firmware!");
  Serial.println("=====================================================");
  Serial.println("");
  
  //Serial.print("Using Rob Tillaarts HX711 library version: ");
  //Serial.println(HX711_LIB_VERSION);
  Serial.println();


  ScanI2C();

}

void ScanI2C(){
  int nDevices = 0;

  Serial.println("Scanning I2C...");

  for (byte address = 1; address < 127; ++address) {
    // The i2c_scanner uses the return value of
    // the Wire.endTransmission to see if
    // a device did acknowledge to the address.
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16) {
        Serial.print("0");
      }
      Serial.print(address, HEX);
      Serial.println("  !");

      ++nDevices;
    } else if (error == 4) {
      Serial.print("Unknown error at address 0x");
      if (address < 16) {
        Serial.print("0");
      }
      Serial.println(address, HEX);
    }
  }
  if (nDevices == 0) {
    Serial.println("No I2C devices found\n");
  } else {
    Serial.println("Done!\n");
  }
}



void ProcessSerialCommands() {
  if (!cmdHandler->readCommand()) return;
  
  // Toggle commands
  if (cmdHandler->is("LoadCellOn")) {
    readLoadCell = true;
  }
  else if (cmdHandler->is("LoadCellOff")) {
    readLoadCell = false;
  }
  else if (cmdHandler->is("SensorsOn")) {
    readSensors = true;
  }
  else if (cmdHandler->is("SensorsOff")) {
    readSensors = false;
  }
  
  // Get/Query commands
  else if (cmdHandler->is("GetLoad")) {
    Serial.print("Load: ");
    Serial.println(force);
  }
  else if (cmdHandler->is("GetTotalAngle")) {
    Serial.print("Total Angle: ");
    Serial.println(totalPosition);
  }
  else if (cmdHandler->is("GetVelocity")) {
    Serial.print("Velocity: ");
    Serial.print(angularSpeed);
    Serial.print("\t");
    Serial.println(averageAngularSpeed);
  }
  else if (cmdHandler->is("GetVersion") || cmdHandler->is("version") || cmdHandler->is("v")) {
    Serial.print("Firmware Version: ");
    Serial.println(FIRMWARE_VERSION);
  }
  else if (cmdHandler->is("GetSteps")) {
    Serial.print("Total Steps: ");
    Serial.println(stepper.readSteps());
  }
  
  // Motor control commands
  else if (cmdHandler->is("Enable")) {
    digitalWrite(ENABLE_PIN, HIGH);
  }
  else if (cmdHandler->is("Disable")) {
    digitalWrite(ENABLE_PIN, LOW);
  }
  else if (cmdHandler->is("Stop")) {
    stepper.rotate(0);
  }
  else if (cmdHandler->is("EStop")) {
    stepper.stop(); // Emergency stop
  }
  else if (cmdHandler->is("Up")) {
    stepper.rotate(-1);
  }
  else if (cmdHandler->is("Down")) {
    stepper.rotate(1);
  }
  else if (cmdHandler->is("Start")) {
    digitalWrite(ENABLE_PIN, HIGH);
    Serial.println("Going Down with 100rpm");
    stepper.setSpeed(1000);
    stepper.rotate(1);
  }
  
  // Parameterized commands
  else if (cmdHandler->startsWith("SetSpeed")) {
    int rpm10 = cmdHandler->getIntParam();
    Serial.print("Setting speed: ");
    Serial.print((float)rpm10 / 10);
    Serial.println(" RPM");
    stepper.setSpeed(rpm10);
  }
  else if (cmdHandler->startsWith("MoveSteps")) {
    long steps = cmdHandler->getLongParam();
    Serial.print("Moving: ");
    Serial.print(steps);
    Serial.println(" steps.");
    stepper.move(steps);
  }
  else if (cmdHandler->startsWith("SetRampLength")) {
    int ramp = cmdHandler->getIntParam();
    Serial.print("Setting ramp length: ");
    Serial.print(ramp);
    Serial.println(" ramp length");
    uint32_t rampLen = stepper.setRampLen(ramp);
    Serial.print("Current rampLen: ");
    Serial.println(rampLen);
  }
}

/*
void Calibrate(){
  Serial.println("\n\n\nCALIBRATION\n===========");
  Serial.println("remove all weight from the loadcell");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("and press enter\n");
  while (Serial.available() == 0);

  Serial.println("Determine zero weight offset");
  LoadCell.tare(20);  // average 20 measurements.
  uint32_t offset = LoadCell.get_offset();

  Serial.print("OFFSET: ");
  Serial.println(offset);
  Serial.println();


  Serial.println("place a weight on the loadcell");
  //  flush Serial input
  while (Serial.available()) Serial.read();

  Serial.println("enter the weight in (whole) grams and press enter");
  uint32_t weight = 0;
  while (Serial.peek() != '\n')
  {
    if (Serial.available())
    {
      char ch = Serial.read();
      if (isdigit(ch))
      {
        weight *= 10;
        weight = weight + (ch - '0');
      }
    }
  }
  Serial.print("WEIGHT: ");
  Serial.println(weight);
  LoadCell.calibrate_scale(weight, 20);
  float scale = LoadCell.get_scale();

  Serial.print("SCALE:  ");
  Serial.println(scale, 15);

  Serial.print("\nuse scale.set_offset(");
  Serial.print(offset);
  Serial.print("); and scale.set_scale(");
  Serial.print(scale, 15);
  Serial.print(");\n");
  Serial.println("in the setup of your project");

  Serial.println("\n\n");
}
*/


