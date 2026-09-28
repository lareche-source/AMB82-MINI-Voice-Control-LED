#include <Arduino.h>
#include <string.h>

// AMB82-MINI Arduino pin numbers, not PCB component labels such as LED4.
const int BLUE_LED = 23;   // PF9 / LED_B
const int GREEN_LED = 24;  // PE6 / LED_G
// Both onboard LEDs are active-high on this AMB82-MINI.
const int BLUE_LED_ON = HIGH;
const int BLUE_LED_OFF = LOW;
const int GREEN_LED_ON = HIGH;
const int GREEN_LED_OFF = LOW;
char buffer[32];
size_t used = 0;
bool overflowed = false;

void execute(const char *command) {
  if (strcmp(command, "BLUE_ON") == 0) digitalWrite(BLUE_LED, BLUE_LED_ON);
  else if (strcmp(command, "BLUE_OFF") == 0) digitalWrite(BLUE_LED, BLUE_LED_OFF);
  else if (strcmp(command, "GREEN_ON") == 0) digitalWrite(GREEN_LED, GREEN_LED_ON);
  else if (strcmp(command, "GREEN_OFF") == 0) digitalWrite(GREEN_LED, GREEN_LED_OFF);
  else if (strcmp(command, "ALL_OFF") == 0) {
    digitalWrite(BLUE_LED, BLUE_LED_OFF);
    digitalWrite(GREEN_LED, GREEN_LED_OFF);
  } else {
    Serial.println("ERR UNKNOWN_COMMAND");
    return;
  }
  Serial.print("OK ");
  Serial.println(command);
}

void setup() {
  pinMode(BLUE_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  digitalWrite(BLUE_LED, BLUE_LED_OFF);
  digitalWrite(GREEN_LED, GREEN_LED_OFF);
  Serial.begin(115200);
  Serial.println("READY VOICE_LED");
}

void loop() {
  while (Serial.available() > 0) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      buffer[used] = '\0';
      if (overflowed) Serial.println("ERR TOO_LONG");
      else if (used > 0) execute(buffer);
      used = 0;
      overflowed = false;
    } else if (!overflowed) {
      if (used < sizeof(buffer) - 1) buffer[used++] = ch;
      else overflowed = true;
    }
  }
  delay(1);
}
