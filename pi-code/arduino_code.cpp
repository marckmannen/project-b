#include <SoftwareSerial.h>
#include <Servo.h>

SoftwareSerial printerSerial(3, 2);
SoftwareSerial scanner(4, 5);
Servo doorServo;

String scannedData = "";
String serialBuffer = "";

const int SERVO_PIN = 9;
const int SERVO_OPEN = 90;
const int SERVO_CLOSE = 0;
const int SERVO_SPEED_MS = 10;  // ms per degree

void moveServo(int targetAngle) {
    int currentAngle = doorServo.read();
    if (currentAngle == targetAngle) return;
    int step = (targetAngle > currentAngle) ? 1 : -1;
    while (currentAngle != targetAngle) {
        currentAngle += step;
        doorServo.write(currentAngle);
        delay(SERVO_SPEED_MS);
    }
}

void setup() {
    Serial.begin(9600);
    printerSerial.begin(19200);
    scanner.begin(9600);
    scanner.listen();
    doorServo.attach(SERVO_PIN);
    doorServo.write(SERVO_CLOSE);
}

void loop() {
    // read from pi
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n') {
            serialBuffer.trim();
            if (serialBuffer == "DOOR:OPEN") {
                moveServo(SERVO_OPEN);
            } else if (serialBuffer == "DOOR:CLOSE") {
                moveServo(SERVO_CLOSE);
            } else if (serialBuffer.length() > 0) {
                printerSerial.listen();
                printerSerial.print(serialBuffer);
                printerSerial.write('\n');
                scanner.listen();
            }
            serialBuffer = "";
        } else {
            serialBuffer += c;
        }
    }

    // scanner
    if (scanner.isListening() && scanner.available()) {
        char c = scanner.read();
        if (isDigit(c)) {
            scannedData += c;
        }
        if (scannedData.length() == 4) {
            Serial.print("SCAN:");
            Serial.println(scannedData);
            scannedData = "";
        }
    }
}