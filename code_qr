#include <SoftwareSerial.h>

SoftwareSerial scanner(10, 11); // RX, TX

String correctPassword = "3043";
String scannedData = "";

void setup() {
  Serial.begin(9600);
  scanner.begin(115200); // try 9600 first, 115200 is often unstable with SoftwareSerial

  Serial.println("QR Scanner ready");
}

void loop() {
  while (scanner.available()) {
    char c = scanner.read();

    Serial.print("RAW: ");
    Serial.println(c);

    if (isDigit(c)) {
      scannedData += c;
    }

    if (scannedData.length() == 4) {
      Serial.print("Scanned: ");
      Serial.println(scannedData);

      if (scannedData == correctPassword) {
        Serial.println("ACCESS GRANTED");
      } else {
        Serial.println("ACCESS DENIED");
      }

      scannedData = "";
      delay(2000);
    }
  }
}
