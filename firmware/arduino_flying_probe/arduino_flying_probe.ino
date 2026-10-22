/*
 * =========================================================================================
 * FPTester Arduino Uno / Nano / Mega Firmware — Dual 5-Bar Linkage Controller
 * =========================================================================================
 * 
 * Hardware:
 *   - Arduino Uno R3, Nano, or Mega 2560
 *   - 4x Servo Motors for 5-Bar Planar Linkage (Arm 0 Left/Right, Arm 1 Left/Right)
 *   - 2x Micro Servos for Z-Axis Probe Needle Extension/Retraction
 *   - 1x Digital Output Pin for Probe Test Voltage Injection (TX Arm)
 *   - 1x Analog ADC Input Pin for Probe Continuity / Voltage Readout (RX Arm)
 *   - 1x Builtin Status LED (Pin 13)
 *
 * Pinout Configuration:
 *   - Arm 0 Motor A (Top Left):    Pin 3  (PWM)
 *   - Arm 0 Motor B (Top Right):   Pin 5  (PWM)
 *   - Arm 1 Motor A (Bottom Left): Pin 6  (PWM)
 *   - Arm 1 Motor B (Bottom Right):Pin 9  (PWM)
 *   - Arm 0 Z-Probe (Needle Up/Down): Pin 10 (PWM)
 *   - Arm 1 Z-Probe (Needle Up/Down): Pin 11 (PWM)
 *   - Test Signal Output (TX Probe):  Pin 12 (Digital Out)
 *   - Test Signal Input (RX Probe):   Pin A0 (Analog ADC)
 *   - Status LED:                     Pin 13
 *
 * Arduino IDE Instructions:
 *   1. Tools -> Board -> Arduino AVR Boards -> "Arduino Uno" (or Nano / Mega)
 *   2. Tools -> Port -> Select your Arduino COM port
 *   3. Click Upload
 *   4. Open Serial Monitor at 115200 baud
 * =========================================================================================
 */

#include <Arduino.h>
#include <Servo.h>

// --- PIN DEFINITIONS ---
#define PIN_SERVO_0A    3   // Arm 0 Left Base Motor
#define PIN_SERVO_0B    5   // Arm 0 Right Base Motor
#define PIN_SERVO_1A    6   // Arm 1 Left Base Motor
#define PIN_SERVO_1B    9   // Arm 1 Right Base Motor
#define PIN_PROBE_Z0    10  // Arm 0 Needle Lower/Raise (Z-axis)
#define PIN_PROBE_Z1    11  // Arm 1 Needle Lower/Raise (Z-axis)
#define PIN_TX_SIGNAL   12  // Probe Inject Signal Output
#define PIN_RX_ADC      A0  // Probe Read ADC Input
#define PIN_LED         13  // Onboard Status LED

// --- SERVO OBJECTS ---
Servo servo0A;
Servo servo0B;
Servo servo1A;
Servo servo1B;
Servo probeZ0;
Servo probeZ1;

// --- Z-AXIS PROBE POSITIONS (Degrees) ---
const int PROBE_UP_ANGLE   = 20;   // Retracted / Travel height
const int PROBE_DOWN_ANGLE = 85;   // Lowered onto PCB pad

// Current servo angles
float currentS0A = 90.0, currentS0B = 90.0;
float currentS1A = 90.0, currentS1B = 90.0;

// Buffer for incoming serial data
String inputString = "";
bool stringComplete = false;

void processCommand(String cmd);
void moveServosSmooth(float t0a, float t0b, float t1a, float t1b, int durationMs = 150);
void lowerProbes();
void raiseProbes();
float readProbeVoltage();

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 1000);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_TX_SIGNAL, OUTPUT);
    digitalWrite(PIN_TX_SIGNAL, LOW);
    pinMode(PIN_RX_ADC, INPUT);

    servo0A.attach(PIN_SERVO_0A, 544, 2400);
    servo0B.attach(PIN_SERVO_0B, 544, 2400);
    servo1A.attach(PIN_SERVO_1A, 544, 2400);
    servo1B.attach(PIN_SERVO_1B, 544, 2400);
    probeZ0.attach(PIN_PROBE_Z0, 544, 2400);
    probeZ1.attach(PIN_PROBE_Z1, 544, 2400);

    raiseProbes();
    moveServosSmooth(90.0, 90.0, 90.0, 90.0, 200);

    // Blink LED 3 times on boot
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); delay(50);
        digitalWrite(PIN_LED, LOW); delay(50);
    }

    Serial.println();
    Serial.println(F("======================================================"));
    Serial.println(F("[ARDUINO] FPTester Dual 5-Bar Flying Probe Controller"));
    Serial.println(F("[ARDUINO] Firmware: v1.2.0 | Baud: 115200 | Status: READY"));
    Serial.println(F("[ARDUINO] Servos: Arm0(D3,D5) Arm1(D6,D9) ProbesZ(D10,D11)"));
    Serial.println(F("[ARDUINO] Ready for test routes from FPTester Web App."));
    Serial.println(F("======================================================"));
}

void loop() {
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        if (inChar == '\n' || inChar == '\r') {
            if (inputString.length() > 0) {
                stringComplete = true;
            }
        } else {
            inputString += inChar;
        }
    }

    if (stringComplete) {
        digitalWrite(PIN_LED, HIGH);
        processCommand(inputString);
        inputString = "";
        stringComplete = false;
        digitalWrite(PIN_LED, LOW);
    }
}

float extractFloat(String src, String key, float defaultVal) {
    int idx = src.indexOf("\"" + key + "\":");
    if (idx == -1) idx = src.indexOf(key + "=");
    if (idx == -1) idx = src.indexOf(key + ":");
    if (idx == -1) return defaultVal;

    int start = src.indexOf(":", idx);
    if (start == -1) start = src.indexOf("=", idx);
    start++;
    while (start < src.length() && (src[start] == ' ' || src[start] == '"')) start++;
    int end = start;
    while (end < src.length() && (isDigit(src[end]) || src[end] == '.' || src[end] == '-')) end++;
    return src.substring(start, end).toFloat();
}

int extractInt(String src, String key, int defaultVal) {
    return (int)extractFloat(src, key, (float)defaultVal);
}

String extractString(String src, String key, String defaultVal) {
    int idx = src.indexOf("\"" + key + "\":");
    if (idx == -1) return defaultVal;
    int start = src.indexOf("\"", idx + key.length() + 3);
    if (start == -1) return defaultVal;
    int end = src.indexOf("\"", start + 1);
    if (end == -1) return defaultVal;
    return src.substring(start + 1, end);
}

void processCommand(String cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;

    if (cmd.equalsIgnoreCase("PING") || cmd.equalsIgnoreCase("?")) {
        Serial.println(F("{\"status\":\"pong\",\"device\":\"ARDUINO_FLYING_PROBE\",\"version\":\"1.2.0\"}"));
        return;
    }

    if (cmd.equalsIgnoreCase("STATUS")) {
        Serial.print(F("{\"status\":\"ready\",\"arm0\":{\"s0a\":"));
        Serial.print(currentS0A);
        Serial.print(F(",\"s0b\":"));
        Serial.print(currentS0B);
        Serial.print(F("},\"arm1\":{\"s1a\":"));
        Serial.print(currentS1A);
        Serial.print(F(",\"s1b\":"));
        Serial.print(currentS1B);
        Serial.println(F("}}"));
        return;
    }

    if (cmd.equalsIgnoreCase("HOME")) {
        raiseProbes();
        moveServosSmooth(90.0, 90.0, 90.0, 90.0, 200);
        Serial.println(F("{\"status\":\"homed\",\"message\":\"Arms returned to 90 deg center datum.\"}"));
        return;
    }

    // FPTester Test Route Command (JSON or G-code)
    if (cmd.indexOf("run_test") != -1 || cmd.indexOf("servo_a_deg") != -1 || cmd.startsWith("G0")) {
        int testId = extractInt(cmd, "test_id", 1);
        String net = extractString(cmd, "net", "NET");
        float expectedMin = extractFloat(cmd, "expected_min_v", 3.0);
        float expectedMax = extractFloat(cmd, "expected_max_v", 5.0);

        float targetS0A = currentS0A;
        float targetS0B = currentS0B;
        float targetS1A = currentS1A;
        float targetS1B = currentS1B;

        int arm0Idx = cmd.indexOf("\"arm_id\": 0");
        if (arm0Idx == -1) arm0Idx = cmd.indexOf("\"arm_id\":0");
        int arm1Idx = cmd.indexOf("\"arm_id\": 1");
        if (arm1Idx == -1) arm1Idx = cmd.indexOf("\"arm_id\":1");

        if (arm0Idx != -1) {
            targetS0A = extractFloat(cmd.substring(arm0Idx), "servo_a_deg", targetS0A);
            targetS0B = extractFloat(cmd.substring(arm0Idx), "servo_b_deg", targetS0B);
        }
        if (arm1Idx != -1) {
            targetS1A = extractFloat(cmd.substring(arm1Idx), "servo_a_deg", targetS1A);
            targetS1B = extractFloat(cmd.substring(arm1Idx), "servo_b_deg", targetS1B);
        }

        if (cmd.indexOf("S0A=") != -1) targetS0A = extractFloat(cmd, "S0A", targetS0A);
        if (cmd.indexOf("S0B=") != -1) targetS0B = extractFloat(cmd, "S0B", targetS0B);
        if (cmd.indexOf("S1A=") != -1) targetS1A = extractFloat(cmd, "S1A", targetS1A);
        if (cmd.indexOf("S1B=") != -1) targetS1B = extractFloat(cmd, "S1B", targetS1B);

        targetS0A = constrain(targetS0A, 15.0, 165.0);
        targetS0B = constrain(targetS0B, 15.0, 165.0);
        targetS1A = constrain(targetS1A, 15.0, 165.0);
        targetS1B = constrain(targetS1B, 15.0, 165.0);

        Serial.print(F("[ARDUINO] Executing Test #"));
        Serial.print(testId);
        Serial.print(F(" (Net: "));
        Serial.print(net);
        Serial.print(F(") -> Arm0: ("));
        Serial.print(targetS0A, 1);
        Serial.print(F("°, "));
        Serial.print(targetS0B, 1);
        Serial.print(F("°) | Arm1: ("));
        Serial.print(targetS1A, 1);
        Serial.print(F("°, "));
        Serial.print(targetS1B, 1);
        Serial.println(F("°)"));

        raiseProbes();
        moveServosSmooth(targetS0A, targetS0B, targetS1A, targetS1B, 150);
        lowerProbes();
        delay(40);

        digitalWrite(PIN_TX_SIGNAL, HIGH);
        delay(10);
        float measuredV = readProbeVoltage();
        int rawADC = analogRead(PIN_RX_ADC);
        digitalWrite(PIN_TX_SIGNAL, LOW);

        raiseProbes();

        String verdict = (measuredV >= expectedMin && measuredV <= expectedMax + 0.5) ? "PASS" : "FAIL";

        Serial.print(F("[ARDUINO] Measurement Result: "));
        Serial.print(measuredV, 2);
        Serial.print(F("V [ADC: "));
        Serial.print(rawADC);
        Serial.print(F("] -> Verdict: "));
        Serial.println(verdict);

        Serial.print(F("{\"status\":\"done\",\"test_id\":"));
        Serial.print(testId);
        Serial.print(F(",\"result\":{\"verdict\":\""));
        Serial.print(verdict);
        Serial.print(F("\",\"adc_voltage\":"));
        Serial.print(measuredV, 3);
        Serial.print(F(",\"adc_raw\":"));
        Serial.print(rawADC);
        Serial.println(F("}}"));
        return;
    }

    Serial.print(F("[ARDUINO] Command received: "));
    Serial.println(cmd);
}

void moveServosSmooth(float t0a, float t0b, float t1a, float t1b, int durationMs) {
    int steps = 10;
    int stepDelay = durationMs / steps;
    float startS0A = currentS0A, startS0B = currentS0B;
    float startS1A = currentS1A, startS1B = currentS1B;

    for (int i = 1; i <= steps; i++) {
        float f = (float)i / (float)steps;
        float angle0A = startS0A + f * (t0a - startS0A);
        float angle0B = startS0B + f * (t0b - startS0B);
        float angle1A = startS1A + f * (t1a - startS1A);
        float angle1B = startS1B + f * (t1b - startS1B);

        servo0A.write((int)round(angle0A));
        servo0B.write((int)round(angle0B));
        servo1A.write((int)round(angle1A));
        servo1B.write((int)round(angle1B));

        delay(stepDelay);
    }

    currentS0A = t0a; currentS0B = t0b;
    currentS1A = t1a; currentS1B = t1b;
}

void lowerProbes() {
    probeZ0.write(PROBE_DOWN_ANGLE);
    probeZ1.write(PROBE_DOWN_ANGLE);
    delay(50);
}

void raiseProbes() {
    probeZ0.write(PROBE_UP_ANGLE);
    probeZ1.write(PROBE_UP_ANGLE);
    delay(50);
}

float readProbeVoltage() {
    long sum = 0;
    for (int i = 0; i < 8; i++) {
        sum += analogRead(PIN_RX_ADC);
        delayMicroseconds(50);
    }
    float avgADC = (float)sum / 8.0;
    return (avgADC / 1023.0) * 5.0; // 10-bit ADC reference to 5.0V
}
