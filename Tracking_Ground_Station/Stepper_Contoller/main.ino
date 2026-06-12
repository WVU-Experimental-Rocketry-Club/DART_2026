#include "Stepper_Controller.h"

void setup() {
  // put your setup code here, to run once:
  if (connect_gps() == 1){
    //Failed to connect to gps
    Serial.println("Failed to Connect to GPS. Check Connection");
    /*
    while(1){
      Serial.println("Failed to Connect to GPS. Check Connection");
      delay(5000);
    }
    */
  }
  Serial2.setTX(4);
  Serial2.setRX(5);
  Serial2.begin(31250);

  //Set up Steppers
  for(int i = 0; i<NUM_STEPPERS; i++){
    steppers.addStepper(stepper[i]);
  }
}

void loop(){
    // put your main code here, to run repeatedly:
  /*
  * Find the azimuth between the ground station and the 
  */
 Serial.println("Hello, World!");


  
  
}