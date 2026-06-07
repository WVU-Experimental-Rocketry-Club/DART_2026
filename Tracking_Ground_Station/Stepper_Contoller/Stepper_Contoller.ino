#include <MultiStepper.h>
#include <AccelStepper.h>
#include <Wire.h> //Needed for I2C to GNSS

#include <SparkFun_u-blox_GNSS_Arduino_Library.h>
#include <Wire.h>

#define NUM_STEPPERS 2

SFE_UBLOX_GNSS myGNSS;
struct gps_location{
  long lat;
  long lon;
  long alt;
};


AccelStepper stepper[NUM_STEPPERS] =
{
  AccelStepper(AccelStepper::DRIVER, 9, 8), // step, dir
  AccelStepper(AccelStepper::DRIVER, 7, 6), // step, dir
};

int connect_gps(){

  Wire.begin();

  //myGNSS.enableDebugging(); // Uncomment this line to enable helpful debug messages on Serial

  if (myGNSS.begin() == false) //Connect to the u-blox module using Wire port
  {
    return 1;
  }

  myGNSS.setI2COutput(COM_TYPE_UBX); //Set the I2C port to output UBX only (turn off NMEA noise)
  myGNSS.saveConfigSelective(VAL_CFG_SUBSEC_IOPORT); //Save (only) the communications port settings to flash and BBR
}
/*
  Returns a struct gps_location that contains lat, long, & alt
  of the ground station.
*/
struct gps_location ground_station_gps(){
  struct gps_location location;

  location.lat = myGNSS.getLatitude();
  location.lon = myGNSS.getLongitude();
  location.alt = myGNSS.getAltitude();
  return location; 
}
// Filled with dummy values for now but will work the same once rex 
// gets it working
struct gps_location rocket_gps(){
  struct gps_location rocket;
  rocket.lat = 36.000;
  rocket.lon = -70.8;
  rocket.alt = 20000;
  return rocket;
}

void setup() {
  // put your setup code here, to run once:
  if (connect_gps() == 1){
    //Failed to connect to gps
  }

  
}

void loop() {
  // put your main code here, to run repeatedly:

}
