#include "Stepper_Controller.h"

volatile double total_phi = 0;
volatile double total_theta = 0;
volatile double theta;
volatile double phi;

location_vector prev_rocket_vector;
location_vector curr_rocket_vector;
location_vector gs_vector;


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
    float speed = (PPR*150)/60;
    stepper[i].setMaxSpeed(speed);
    steppers.addStepper(stepper[i]);

  }
  //Sets the previous rocket vector as the intial location on the ground station
  prev_rocket_vector = get_rocket_vector();
  gs_vector = get_ground_vector();                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
}

void loop(){
  // put your main code here, to run repeatedly:
  curr_rocket_vector = get_rocket_vector();
  

  
  //Calc A
  double mag_A = get_magnitude(gs_vector,prev_rocket_vector);
  //Calc B
  double mag_B = get_magnitude(gs_vector,curr_rocket_vector);
  //Calc C
  double mag_C = get_magnitude(prev_rocket_vector,curr_rocket_vector);

  //Calc Theta (Horizantel Angle)
  theta = acos((pow(mag_A,2)+pow(mag_B,2)-pow(mag_C,2))/(2*mag_A*mag_B));
  //Calc delta Phi (Verticle Angle)
  double curr_Z = curr_rocket_vector.z;
  double prev_Z = prev_rocket_vector.z;

  phi = atan( ((curr_Z/mag_B) - (prev_Z/mag_A)) / (1+((curr_Z*prev_Z)/(mag_A*mag_B))) );

  total_phi += phi;
  total_theta += theta;
}

void loop1(){
  if(total_phi >= MAX_PHI || total_theta >= MAX_THETA){
    //ERROR- THe bounds have been reached 
  }
  else{
    //MAX does not conflict, continue with step
    step_to_rocket(phi,theta);
  }
}