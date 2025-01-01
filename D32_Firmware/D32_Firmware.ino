#include <HX711.h> // https://github.com/RobTillaart/HX711

#include <Wire.h>
#include <MobaTools.h>
#include "Sensors.h"



#define DATA_PIN    16     // HX711
#define CLOCK_PIN   4      // HX711
#define STEP_PIN   14      // Stepper driver step pin
#define DIR_PIN    27      // Stepper driver direction  pin
#define ENABLE_PIN 26      // Stepper driver enable pin

const int SPEED_SWITCH_PIN = 2; // HIGH is slow 
const int UP_BUTTON_PIN    = 0;
const int DOWN_BUTTON_PIN  = 15;


#define TCAADDR 0x70 // I2C multiplexer adress
#define NUMBER_READINGS 20

bool readLoadCell = false;
bool readAngle = false;
bool readAngularSpeed = false;

unsigned long delayTime = millis();
float currentAngle[2] =   {0.0, 0.0};
float previousAngle[2] =   {0.0, 0.0};
float angularSpeed[2]  =   {0.0, 0.0};
float angleDiff[2]     =   {0.0, 0.0};
float previousAngleDiff[2] = {10.0, 10.0};
unsigned long previousTime[2] = {0, 0}; 
float dt[2] = {0, 0};
float previousDt[2] = {0, 0};
int rotDir = 1;
float averageAngularSpeed[2];      // Averaged angular speed values
float angularSpeedBuffer[2][NUMBER_READINGS];    // Circular buffer for storing readings
int bufferIndex = 0;               // Index to track the position in the buffer
float totalAngle[2] = {0, 0};
long force = 0;


bool speedSwitchState = HIGH; // HIGH is slow and default
bool upButtonState = HIGH;
bool lastUpButtonState = HIGH;
bool downButtonState = HIGH;
bool lastDownButtonState = HIGH;

// Variables for debouncing
unsigned long lastUpDebounceTime = 0;
unsigned long lastDownDebounceTime = 0;
const unsigned long debounceDelay = 800; // Debounce time in milliseconds

HX711 LoadCell;

Sensors sensors; // Rotation sensors

const int STEPS_REVOLUTION = 200*8;
MoToStepper stepper( STEPS_REVOLUTION, STEPDIR ); // Mode is stepdir


void setup() {
  Wire.begin();
  Serial.begin(9600);
  while (!Serial);

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(SPEED_SWITCH_PIN, INPUT_PULLUP);
  pinMode(UP_BUTTON_PIN, INPUT_PULLUP);
  pinMode(DOWN_BUTTON_PIN, INPUT_PULLUP);

  LoadCell.begin(DATA_PIN, CLOCK_PIN, true);
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
  
  stepper.setRampLen(300);
  // Ramp length in steps. The permissible ramp length depends on the step rate, and a
  // maximum of 16000 for high step rates. For step rates below 2steps/sec, ramping is no
  // longer possible. If ramplen is outside the permissible range, the value is adjusted.

  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW); 
  

  // Initialize arrays
  for (int i = 0; i < NUMBER_READINGS; i++) {
    angularSpeedBuffer[0][i] = 0.0;
    angularSpeedBuffer[1][i] = 0.0;
  }


  DisplayHelp();
}

void loop() {
  ReadSerial();
  CheckButtonStates();

  //OldMethod();
  // Only read data when it is already available.
  if (LoadCell.is_ready()) {
    force = LoadCell.read();
  }
  NewMethod();
}

void NewMethod(){

  if ( millis() - delayTime > 50 ) { 
    delayTime = millis();
    
    if (readLoadCell){
      Serial.print(force); Serial.print("\n");
    }  

    for (int i = 0; i < 2; i++){
      if (readAngle){
        Serial.print(currentAngle[i]); Serial.print("\t");           // current angle
      }
        
      if (readAngularSpeed){
        Serial.print(angleDiff[i]); Serial.print("\t");              // angle difference
        Serial.print(dt[i]); Serial.print("\t");                     // time difference
        Serial.print(angularSpeed[i]); Serial.print("\t");           // Angular speed
      }
    }
    if (readAngle || readAngularSpeed){
      Serial.print("\n");
    }

  }

  for (int i = 0; i < 2; i++){
    unsigned long currentTime = micros(); // Use micros() for higher precision
    currentAngle[i] = sensors.getAngle(i); // Read the raw sensor angle (0-360 range)
    angleDiff[i] = currentAngle[i] - previousAngle[i]; // Compare raw angles

    // Handle 360-degree wrap-around for the raw angle difference
    if (rotDir > 0){
      angleDiff[i] = (float)((int) (angleDiff[i] * 100 + 36000) % 36000) / 100;
    } else if(rotDir < 0) {
      angleDiff[i] = previousAngle[i] - currentAngle[i];
      angleDiff[i] = - (float)((int) (angleDiff[i] * 100 + 36000) % 36000) / 100;
    } else{
      angleDiff[i] = 0;
    }

    

    // Calculate time difference
    dt[i] = (currentTime - previousTime[i]) / 1000000.0; // Convert micros to seconds
    if (dt[i] > 5*previousDt[i]) {
      previousAngle[i] = currentAngle[i];
      previousTime[i] = currentTime; 
      previousDt[i] = dt[i];
      return;
    }

    if (abs(angleDiff[i]) > 30){
      previousAngle[i] = currentAngle[i];
      previousTime[i] = currentTime; 
      previousDt[i] = dt[i];
      previousAngleDiff[i] = angleDiff[i];
      return;
    }

    totalAngle[i] += angleDiff[i];

    // Compute angular speed
    angularSpeed[i] = angleDiff[i] / dt[i] / 6; // RPM

    // Add new readings to the circular buffer
    angularSpeedBuffer[i][bufferIndex] = angularSpeed[i];

    // Increment the buffer index (wrap around using modulo)
    bufferIndex = (bufferIndex + 1) % NUMBER_READINGS;
    
    // Calculate the average of the last N readings
    averageAngularSpeed[i] = Average(angularSpeedBuffer[i]);

    // Update previous values for the next iteration
    previousAngle[i] = currentAngle[i];
    previousTime[i] = currentTime; 
    previousDt[i] = dt[i];
    previousAngleDiff[i] = angleDiff[i];
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

void OldMethod(){
  if ( millis() - delayTime > 10 ) {  // Run every 10ms
    delayTime = millis();

    AngularSpeed();

    if (readLoadCell){
      // Only read data when it is already available.
      if (LoadCell.is_ready()) {
        Serial.print(LoadCell.read()); Serial.print("\t");
      }
    }
    
    if (readLoadCell || readAngle || readAngularSpeed){
      Serial.print("\n");
    }

    
  }
}

void CheckButtonStates(){
  speedSwitchState         = digitalRead(SPEED_SWITCH_PIN);
  bool rawUpButtonState    = digitalRead(UP_BUTTON_PIN);
  bool rawDownButtonState  = digitalRead(DOWN_BUTTON_PIN);
  
  // Check if the button state has changed
  if (upButtonState != lastUpButtonState) {
    lastUpButtonState = millis(); // Reset the debounce timer
  }
  // Check if the button state has changed
  if (downButtonState != lastDownButtonState) {
    lastDownButtonState = millis(); // Reset the debounce timer
  }

  // Check if enough time has passed to consider the input stable
  if ((millis() - lastUpButtonState) > debounceDelay) {
    // If the state has stabilized, update the button state
    if (rawUpButtonState != upButtonState) {
      upButtonState = rawUpButtonState;

      // Detect button press (LOW to HIGH transition)
      if (upButtonState == LOW) {
        MoveUp();
      }

      // Detect button release (HIGH to LOW transition)
      if (upButtonState == HIGH) {
        Stop();
      }
    }
  }
  // Update the last button state for the next loop
  lastUpButtonState = upButtonState;



  // Check if enough time has passed to consider the input stable
  if ((millis() - lastDownButtonState) > debounceDelay) {
    // If the state has stabilized, update the button state
    if (rawDownButtonState != downButtonState) {
      downButtonState = rawDownButtonState;
      
      // Detect button press (LOW to HIGH transition)
      if (downButtonState == LOW) {
        MoveDown();
      }

      // Detect button release (HIGH to LOW transition)
      if (downButtonState == HIGH) {
        Stop();
      }
    }
  }
  // Update the last button state for the next loop
  lastDownButtonState = downButtonState;
}

void MoveUp(){
  digitalWrite(ENABLE_PIN, HIGH);
  if (speedSwitchState == LOW){
    Serial.println("Going up fast!");
    stepper.setSpeed(3000);
  } else{
    Serial.println("Going up!");
    stepper.setSpeed(300);
  }
  
  stepper.rotate(1);
  rotDir = 1;
  
}

void MoveDown(){
  digitalWrite(ENABLE_PIN, HIGH);
  if (speedSwitchState == LOW){
    Serial.println("Going down fast!");
    stepper.setSpeed(3000);
  } else{
    Serial.println("Going down!");
    stepper.setSpeed(300);
  }

  stepper.rotate(-1);
  rotDir = -1;
}

void Stop(){
  Serial.println("");
  Serial.println("");
  Serial.println("Stop and halt!");

  stepper.rotate(0);
  rotDir = 0;
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

void AngularSpeed(){
  // subtract the last reading:
  for (int i = 0; i < 2; i++){
    unsigned long currentTime = micros(); // Use micros() for higher precision

    currentAngle[i] = sensors.getAngle(i); // Read the raw sensor angle (0-360 range)
    angleDiff[i] = currentAngle[i] - previousAngle[i]; // Compare raw angles

    // Handle 360-degree wrap-around for the raw angle difference
    if (rotDir > 0){
      angleDiff[i] = (float)((int) (angleDiff[i] * 100 + 36000) % 36000) / 100;
    } else if(rotDir < 0) {
      angleDiff[i] = previousAngle[i] - currentAngle[i];
      angleDiff[i] = - (float)((int) (angleDiff[i] * 100 + 36000) % 36000) / 100;
    } else{
      angleDiff[i] = 0;
    }

    // Calculate time difference
    dt[i] = (currentTime - previousTime[i]) / 1000000.0; // Convert micros to seconds
    if (dt[i] > 5*previousDt[i]) {
      previousAngle[i] = currentAngle[i];
      previousTime[i] = currentTime; 
      previousDt[i] = dt[i];
      return;
    }

    // Compute angular speed
    angularSpeed[i] = angleDiff[i] / dt[i] / 6; // RPM

    // Update previous values for the next iteration
    previousAngle[i] = currentAngle[i];
    previousTime[i] = currentTime; 
    previousDt[i] = dt[i];
    
  }

  for (int i = 0; i < 2; i++){
    if (readAngle){
      Serial.print(currentAngle[i]); Serial.print("\t");           // current angle
    }
      
    if (readAngularSpeed){
      //Serial.print(angleDiff[i]); Serial.print("\t");              // angle difference
      //Serial.print(dt[i]); Serial.print("\t");                     // time difference
      Serial.print(angularSpeed[i]); Serial.print("\t");           // Angular speed
    }
  }

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

void ReadSerial() {
  if( !Serial.available() ){ return; }
  
  String command = Serial.readStringUntil('\n');
  //Serial.println("Command recieved: " + command);
  
  if(command == "LoadCellOn"){
    readLoadCell = true;
  }

  else if(command == "LoadCellOff"){
    readLoadCell = false;
  }

  else if(command == "AngleOn"){
    readAngle = true;
  }

  else if(command == "AngleOff"){
    readAngle = false;
  }

  else if(command == "VelocityOn"){
    readAngularSpeed = true;
  }

  else if(command == "VelocityOff"){
    readAngularSpeed = false;
  }

  else if(command == "GetLoad"){
    Serial.print("Load: "); Serial.println(force);
  }
  else if(command == "GetTotalAngle"){
    Serial.print("Total Angle: "); 
    Serial.print(totalAngle[0]); Serial.print("\t"); 
    Serial.print(totalAngle[1]); Serial.print("\n"); 
  }
  else if(command == "GetVelocity"){
    Serial.print("Velocity: "); 
    Serial.print(averageAngularSpeed[0]); Serial.print("\t"); 
    Serial.print(averageAngularSpeed[1]); Serial.print("\n"); 
  }

  else if(command == "Enable"){
    //Serial.println("Enabling motors.");
    digitalWrite(ENABLE_PIN, HIGH);
  }

  else if(command == "Disable"){
    //Serial.println("Disabling motors.");
    digitalWrite(ENABLE_PIN, LOW);
    rotDir = 0;
  }

  else if(command == "Stop"){
    //Serial.println("Stopping...");
    stepper.rotate(0);
    rotDir = 0;
  }

  else if(command == "EStop"){
    //Serial.println("Emergency stop!");
    stepper.stop(); //Emergency stop
    rotDir = 0;
  }

  else if(command =="Forward"){
    //Serial.println("Going Forward...");
    stepper.rotate(1);
    rotDir = 1;
  }

  else if(command == "Backward"){
    //Serial.println("Going Backwards...");
    stepper.rotate(-1);
    rotDir = -1;
  }

  else if(command == "Start"){
    digitalWrite(ENABLE_PIN, HIGH);
    stepper.setSpeed(1000);
    stepper.rotate(1);
    rotDir = 1;
  }

  else if(command.indexOf("SetSpeed") > -1){ //RPM
    Serial.print("Setting speed: ");
    int ind = command.indexOf(' ');  //finds location of first ' '
    String sval = command.substring(ind+1);
    int rpm10 = sval.toInt(); 
    Serial.print((float)rpm10/10); Serial.print(" RPM\n");
    stepper.setSpeed(rpm10); // revolution per minute times 10
  }

  else if(command.indexOf("SetRampLength") > -1){ 
    // Ramp length in steps. The permissible ramp length depends on the step rate, and a
    // maximum of 16000 for high step rates. For step rates below 2steps/sec, ramping is no
    // longer possible. If ramplen is outside the permissible range, the value is adjusted.

    Serial.print("Setting ramp length: ");
    int ind = command.indexOf(' ');  //finds location of first ' '
    String sval = command.substring(ind+1);
    int ramp = sval.toInt(); 
    Serial.print(ramp); Serial.print(" ramp length\n");
    stepper.setRampLen(ramp);
  }
  
  else if(command == "GetSteps"){
    Serial.print("Total Steps: ");
    Serial.println(stepper.readSteps());
  }

  else{
    //Serial.println("Unrecognized command.");
    //DisplayHelp();
  }

}

/*
void Calibrate(){
  Serial.println("\n\nCALIBRATION\n===========");
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

void DisplayHelp() {
  Serial.println("----------------------");
  Serial.println("Valid Commands are:");
  Serial.println("");
  Serial.println("'GetLoad'                     - Returns the latest load cell reading");
  Serial.println("'GetVelocity'                 - Returns the angular velocty of each sensor");
  Serial.println("'GetTotalAngle'               - Returns the total change of the angle since start");
  Serial.println("'GetSteps'                    - Returns the total number of steps since start");
  Serial.println("'Enable' / 'Disable'          - Enables/Disables the motors");
  Serial.println("'Stop'                        - Slows the motors to a stop");
  Serial.println("'EStop'                       - Breaks to motors to a stop immediately");
  Serial.println("'SetSpeed' <RPM*10>           - Sets the rotational speed to rpm times 10. ");
  Serial.println("'Forward' / 'Backward'        - Moves the motors");
  Serial.println("'Start'                       - Start rotating the motors at 100 rpm forward");
  Serial.println("'LoadCellOn' / 'LoadCellOff'  - Continuous reading every 50ms");
  Serial.println("'AngleOn' / 'AngleOff'        - Continuous reading every 50ms");
  Serial.println("'VelocityOn' / 'VelocityOff'  - Continuous reading every 50ms");
  Serial.println("----------------------");
}
