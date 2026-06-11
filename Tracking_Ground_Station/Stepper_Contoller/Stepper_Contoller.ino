#include <MultiStepper.h>
#include <AccelStepper.h>
#include <Wire.h> //Needed for I2C to GNSS

#include <SparkFun_u-blox_GNSS_Arduino_Library.h>
#include <Wire.h>

#define NUM_STEPPERS 2
#define PPR 400
#define MAX_verticle_angle 89
#define MAX_AZIMUTH 180
#define EARTH_RADIUS 6378
SFE_UBLOX_GNSS myGNSS;

typedef struct gps_location{
  double lat;
  double lon;
  double alt;
}gps_location;


AccelStepper stepper[NUM_STEPPERS] =
{
  AccelStepper(AccelStepper::DRIVER, 9, 8), // step, dir    verticle_angle
  AccelStepper(AccelStepper::DRIVER, 7, 6), // step, dir    AZIMUTH
};

MultiStepper steppers;

double total_verticle_angle = 0;
double total_azimuth = 0;

/*
  Initializes and connect to the UBLOX GPS
*/
int connect_gps(){

  Wire.begin();

  //myGNSS.enableDebugging(); // Uncomment this line to enable helpful debug messages on Serial

  if (myGNSS.begin() == false) //Connect to the u-blox module using Wire port
  {
    return 1;
  }

  myGNSS.setI2COutput(COM_TYPE_UBX); //Set the I2C port to output UBX only (turn off NMEA noise)
  myGNSS.saveConfigSelective(VAL_CFG_SUBSEC_IOPORT); //Save (only) the communications port settings to flash and BBR
  return 0;
}
/*
  Returns a struct gps_location that contains lat, long, & alt
  of the ground station.
*/
struct gps_location ground_station_gps(){
  struct gps_location location;
  /*
  location.lat = myGNSS.getLatitude() * 10000000;
  location.lon = myGNSS.getLongitude() * 10000000;
  location.alt = myGNSS.getAltitudeMLS() / 1000;
  */
  location.lat = 32.0000;
  location.lon = -102.0833;
  location.alt = 200;
  return location; 
}

// Filled with dummy values for now but will work the same once rex 
// gets it working
struct gps_location rocket_gps(){
  struct gps_location rocket;
  rocket.lat = 32.0050;
  rocket.lon = -102.0800;
  rocket.alt = 20000;
  return rocket;
}

double get_azimuth(){
  struct gps_location rocket = rocket_gps();
  struct gps_location ground = ground_station_gps();
  //Get Latitude values for rocket and ground station in radians
  //Compute Diffrence between rocket and ground longitude in radians
  double rocket_lat = rocket.lat*(PI/180);
  double ground_lat = ground.lat*(PI/180);
  double delta_long = (rocket.lon - ground.lon)*(PI/180);

  double X = sin(delta_long)*cos(rocket_lat);
  double Y= (cos(ground_lat)*sin(rocket_lat))-(sin(ground_lat)*cos(rocket_lat)*cos(delta_long));
  double theta = atan2(X,Y) * (180/PI);
  double azimuth = fmod(theta +360.0,360.0);
  //Azimuth debug statments
  /*
    //Display Rocket
    
    Serial.println("        Rocket        ");
    Serial.print("  Latitude:   ");
    Serial.println(rocket.lat);
    Serial.print("  Longitude:  ");
    Serial.println((rocket.lon));

    //Display Ground
    Serial.println("      Ground Station        ");
    Serial.print("  Latitude:   ");
    Serial.println(rocket.lat);
    Serial.print("  Longitude:  ");
    Serial.println((ground.lon));

    Serial.print("Azimuth:              ");
    Serial.println(azimuth);
    delay(10000);
  */
  return azimuth;
}
double get_verticle_angle(){
  gps_location rocket = rocket_gps();
  gps_location ground = ground_station_gps();

  // Get Rocket Cords
  double rocket_lat = rocket.lat;
  double rocket_lon = rocket.lon;
  double rocket_alt = rocket.alt;

  //Get Grounds Cords
  double ground_lat = ground.lat;
  double ground_lon = ground.lon;
  double ground_alt = ground.alt;

  //Calculate distance using Haversine Formula
  double Distance = 2 * EARTH_RADIUS * asin(sqrt( pow(sin( (rocket_lat-ground_lat)/2 ), 2) + cos(ground_lat)*cos(rocket_lat)* pow(sin((rocket_lat-ground_lon))/2,2 )));

  double verticle_angle = atan((rocket_alt/ground_alt)/Distance);

  return verticle_angle;


}
void step_to_rocket(double verticle_angle, double azimuth){
  double step_angle = 360/PPR;
  double verticle_angle_steps = step_angle/verticle_angle; // Vertivle angle
  double azimuth_steps = step_angle/azimuth; // Horizontale angle

  long positions[2] = {(long)verticle_angle_steps, (long)azimuth_steps};

  steppers.moveTo(positions);
  steppers.runSpeedToPosition();

  
}
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

void loop() {
  // put your main code here, to run repeatedly:
  /*
  * Find the azimuth between the ground station and the 
  */
  double azimuth = get_azimuth();
  Serial.println(azimuth);


  
  
}
