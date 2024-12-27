//#include <Stepper.h>
#include <AccelStepper.h>
#include <HX711.h>


#define DOUT 11
#define CLK 12
#define ledPin 13
#define downBtnPin 4
#define speedSwitchPin 3
#define upBtnPin 2
#define stepPin 8
#define dirPin 9


const int slow = 1;
const int fast = 0;
int switchState = LOW;
 

HX711 loadCell;

String command;

bool displayLoad = false;
unsigned long timer1 = 0;
unsigned long timer2 = 0;
unsigned long timer3 = 0;
unsigned long timer4 = 0;

#define PITCH 5 // 5mm
#define GEAR_RATIO 20 //1:20
unsigned int rpm = 300; // max rpm = 300

#define STEPS_PER_REVOLUTION 12800 // 800 steps is one revolution of motor
#define STEPS_PER_OUT_REVOLUTION 256000

//Stepper stepper(STEPS_PER_REVOLUTION, stepPin, dirPin);
AccelStepper stepper(AccelStepper::DRIVER, stepPin, dirPin);

long isteps; 


void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);

  Serial.println("Welcome to the Universal Test Machine interface.");
  Serial.println("------------------------------------------------");
  Serial.println(" ");
  DisplayHelp();

  loadCell.begin(DOUT, CLK);

  delay(1000);
  Serial.println(loadCell.is_ready());
  loadCell.set_offset(-1404);
  loadCell.set_scale(-1.56);


  pinMode(upBtnPin, INPUT_PULLUP);
  pinMode(downBtnPin, INPUT_PULLUP);
  pinMode(speedSwitchPin, INPUT_PULLUP);
  
  Serial.println("Max rpm for steppers is 300!");
  rpm = 300;
  // stepper.setSpeed(rpm);
  stepper.setMaxSpeed(500);
  stepper.setAcceleration(1000);

  float v_a = AxialSpeed(rpm);
  Serial.print("Axial speed: ");
  Serial.println(v_a);

  ComputeRPM(v_a);
  Serial.print("rpm: ");
  Serial.println(rpm);

  switchState = digitalRead(speedSwitchPin);
}

int MMtoSteps(float u) {
  return round((float)(STEPS_PER_OUT_REVOLUTION / PITCH) * u);
}

float AxialSpeed(unsigned int rpm) {
  return rpm * (float)1/GEAR_RATIO * PITCH / 60;
}

void ComputeRPM(float axial_speed){
  rpm = round(60 * axial_speed / ((float)1/GEAR_RATIO * PITCH));

  if(rpm > 300){
    Serial.println("Warning, speed limit of 1.25mm/s and 300rpm reached!");
    rpm = 300;
  }
}


int roundTo (int a, int roundTo) {
  return a >= 0 ? (a+2)/roundTo*roundTo : (a-2)/roundTo*roundTo ;
}

void DisplayHelp() {
  Serial.println(" ");
  Serial.println("Type 'h' or 'help' to display the help.");
  Serial.println("Commands: ");
  Serial.println("'Calibrate Loadcell' or 'C' ");
  Serial.println("'L' to display loadcell data");
  Serial.println("'T' to tare loadcell");
  Serial.println("'rpm x' to set the rpm to x");
}

void CalibrateLoadcell() {
  Serial.println("This will calibrate the loadcell. Yes to continue.");
  while(Serial.available() == 0) {}
  String ret = Serial.readStringUntil('\n');
  if( !ret.equalsIgnoreCase("Yes") ){
    Serial.println("Abort.");
    DisplayHelp();
    return;
  }
      
  Serial.println("\nRemove any load from the load cell, press return to continue");
  while(Serial.available() == 0) {}
  Serial.readStringUntil('\n');
  loadCell.tare();
  Serial.print("UNITS: ");
  long offSet=loadCell.get_units(10);
  Serial.println(offSet);

  Serial.println("\nType the amount of mass in grams and put the mass on the loadcell to load it in compression.");
  while(Serial.available() == 0) {}
  String calibrationLoad = Serial.readStringUntil('\n');
  int icalibrationLoad = calibrationLoad.toInt();
  Serial.print("Load: ");
  Serial.print(icalibrationLoad);
  Serial.println(" g.");

  loadCell.calibrate_scale(icalibrationLoad, 5);
  
  Serial.println("\nLoadcell is calibrated, your calibration values:");
  long scaleOffset = loadCell.get_offset();
  Serial.print("\nOffset \t");
  Serial.println(scaleOffset);

  float scaleFactor = loadCell.get_scale();
  Serial.print("Scale \t");
  Serial.println(scaleFactor);

  
}

void loop() {
  // put your main code here, to run repeatedly:
  if(Serial.available()){
    command = Serial.readStringUntil('\n');
    Serial.println("Command recieved: " + command);
  }

  if(command.equalsIgnoreCase("h") || command.equalsIgnoreCase("help") ){
      DisplayHelp();
  }

  if(command.equalsIgnoreCase("Calibrate Loadcell") || command.equalsIgnoreCase("C") ){
     CalibrateLoadcell();  
  }

  if(command.equalsIgnoreCase("L") ){
      if (displayLoad){
        displayLoad = false;
      }else{
        displayLoad = true;
      }
  }
  if(command.equalsIgnoreCase("T") ){
    loadCell.tare();
  }


  if(command.indexOf("setSpeed") > -1){
    int ind = command.indexOf(' ');  //finds location of first ' '
    float speed = 800; // steps per second, 1/4 rev per second, max 1000
    // The desired constant speed in steps per second. Positive is clockwise. 
    // Speeds of more than 1000 steps per second are unreliable. 
    //Very slow speeds may be set (eg 0.00027777 for once per hour, approximately. 
    // Speed accuracy depends on the Arduino crystal. Jitter depends on how frequently you call the runSpeed() function. 
    // The speed will be limited by the current value of setMaxSpeed()
    if(ind > 0){ // value was provided
      String val = command.substring(ind+1);
      speed = val.toFloat();
    }
    stepper.setSpeed(speed);
  }
  if(command.indexOf("setMaxSpeed") > -1){
    int ind = command.indexOf(' ');  //finds location of first ' '
    float speed = 800; // Sets the maximum permitted speed. The run() function will accelerate up to the speed set by this function.
    // speed	The desired maximum speed in steps per second.  Must be > 0.
    // Speeds of more than 1000 steps per second are unreliable. 
    // Caution: Speeds that exceed the maximum speed supported by the processor may Result in non-linear accelerations and decelerations.

    if(ind > 0){ // value was provided
      String val = command.substring(ind+1);
      speed = val.toFloat();
    }
    stepper.setMaxSpeed(speed);
  }
  if(command.indexOf("setAcceleration") > -1){
    int ind = command.indexOf(' ');  //finds location of first ' '
    float acc = 1000; // The desired acceleration in steps per second per second. Must be > 0.0. 
    // This is an expensive call since it requires a square root to be calculated. Dont call more ofthen than needed

    if(ind > 0){ // value was provided
      String val = command.substring(ind+1);
      acc = val.toFloat();
    }
    stepper.setAcceleration(acc);
  }


  if(command.indexOf("forward") > -1){
    int ind = command.indexOf(' ');  //finds location of first ' '

    long steps = 200*16; // one rev
    if(ind > 0){ // val was provided
      String val = command.substring(ind+1);
      steps = val.toInt();
    }
    Serial.print("steps: ");
    Serial.println(steps);
    stepper.move(steps);

    Serial.println("done!");
  }
  if(command.indexOf("backward") > -1){
    int ind = command.indexOf(' ');  //finds location of first ' '

    long steps = -200*16; // one rev
    if(ind > 0){ // val was provided
      String val = command.substring(ind+1);
      steps = -val.toInt();
    }
    Serial.print("steps: ");
    Serial.println(steps);
    stepper.move(steps);

    Serial.println("done!");
  }
  if(command.equalsIgnoreCase("stop") ){
    stepper.stop();
  }

  stepper.run();




  if( displayLoad) {
    if ((millis() - timer1) > 100) {
      float rawVal = loadCell.get_units(1);
      
      int val = round(rawVal / 1000 * 9.82); //N whole

      //int val = roundTo(val,10); //Round to nearest 10N

      
      Serial.println(val);
      timer1 = millis();
    }
  }
  
 /*  // UP
  if( (millis()-timer3) > 50 ){
    timer3 = millis();
    if (digitalRead(upBtnPin) == LOW) {
      Serial.println("Up");
      if( switchState == fast) {
        isteps = MMtoSteps(1.0);
        Serial.print("steps: ");
        Serial.println(isteps);
        stepper.step(isteps);
      } else{
        isteps = MMtoSteps(0.01);
        Serial.print("steps: ");
        Serial.println(isteps);
        stepper.step(isteps);
      }
      
    }
  }

  //Down
  if( (millis()-timer4) > 50 ){
    timer4 = millis();
    if (digitalRead(downBtnPin) == LOW) {
      Serial.println("Down");
      if( switchState == fast) {
        isteps = -MMtoSteps(1.0);
        Serial.print("steps: ");
        Serial.println(isteps);
        stepper.step(isteps);
      } else{
        isteps = -MMtoSteps(0.01);
        Serial.print("steps: ");
        Serial.println(isteps);
        stepper.step(isteps);
      }
    }
  } */



  if( (millis()-timer2) > 50 ){
    if( digitalRead(speedSwitchPin) != switchState ) {
      
      switchState = digitalRead(speedSwitchPin);

      Serial.println(switchState);
    }
    timer2 = millis();
  }
  

  command = "";
}
