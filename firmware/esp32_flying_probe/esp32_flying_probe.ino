/*
 * =========================================================================================
 * FPTester ESP32 Firmware — Automated Flying Probe Dual 5-Bar Linkage Kinematics Controller
 * =========================================================================================
 * 
 * Hardware:
 *   - ESP32 Development Module (ESP32-WROOM-32 / ESP32-S3)
 *   - 4x Servo Motors for 5-Bar Planar Linkage (Arm 0 Left/Right, Arm 1 Left/Right)
 *   - 2x Micro Servos or Solenoids for Z-Axis Probe Needle Extension/Retraction
 *   - 1x Digital Output Pin for Probe Test Voltage Injection (TX Arm)
 *   - 1x Analog ADC Input Pin for Probe Continuity / Voltage Readout (RX Arm)
 *   - 1x Status Indicator LED (GPIO 2)
 *
 * Pinout Configuration:
 *   - Arm 0 Motor A (Top Left):    GPIO 18
 *   - Arm 0 Motor B (Top Right):   GPIO 19
 *   - Arm 1 Motor A (Bottom Left): GPIO 21
 *   - Arm 1 Motor B (Bottom Right):GPIO 22
 *   - Arm 0 Z-Probe (Needle Up/Down): GPIO 23
 *   - Arm 1 Z-Probe (Needle Up/Down): GPIO 25
 *   - Test Signal Output (TX Probe):  GPIO 32 (3.3V Pulse)
 *   - Test Signal Input (RX Probe):   GPIO 34 (ADC1 Channel 6)
 *   - Status LED:                     GPIO 2
 *
 * Arduino IDE Instructions:
 *   1. Tools -> Board -> ESP32 Arduino -> "ESP32 Dev Module"
 *   2. Tools -> Upload Speed -> "921600"
 *   3. Tools -> Port -> Select your ESP32 COM port
 *   4. Install "ESP32Servo" library via Library Manager (Sketch -> Include Library -> Manage Libraries)
 *   5. Click Upload
 *   6. Open Serial Monitor at 115200 baud
 * =========================================================================================
 */

#include <Arduino.h>
#include <ESP32Servo.h>

// --- PIN DEFINITIONS ---
#define PIN_SERVO_0A    18  // Arm 0 Left Base Motor
#define PIN_SERVO_0B    19  // Arm 0 Right Base Motor
#define PIN_SERVO_1A    21  // Arm 1 Left Base Motor
#define PIN_SERVO_1B    22  // Arm 1 Right Base Motor
#define PIN_PROBE_Z0    23  // Arm 0 Needle Lower/Raise (Z-axis)
#define PIN_PROBE_Z1    25  // Arm 1 Needle Lower/Raise (Z-axis)
#define PIN_TX_SIGNAL   32  // Probe Inject Signal Output
#define PIN_RX_ADC      34  // Probe Read ADC Input
#define PIN_LED         2   // Onboard Status LED

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

// Function prototypes
void processCommand(String cmd);
void moveServosSmooth(float t0a, float t0b, float t1a, float t1b, int durationMs = 150);
void lowerProbes();
void raiseProbes();
float readProbeVoltage();

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 1000); // Allow USB serial to stabilize

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_TX_SIGNAL, OUTPUT);
    digitalWrite(PIN_TX_SIGNAL, LOW);
    pinMode(PIN_RX_ADC, INPUT);
    analogReadResolution(12); // 12-bit ADC (0 - 4095, 0.0V - 3.3V)

    // Allow allocation of all timers for ESP32 servos
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    ESP32PWM::allocateTimer(2);
    ESP32PWM::allocateTimer(3);

    servo0A.setPeriodHertz(50);
    servo0B.setPeriodHertz(50);
    servo1A.setPeriodHertz(50);
    servo1B.setPeriodHertz(50);
    probeZ0.setPeriodHertz(50);
    probeZ1.setPeriodHertz(50);

    servo0A.attach(PIN_SERVO_0A, 500, 2400);
    servo0B.attach(PIN_SERVO_0B, 500, 2400);
    servo1A.attach(PIN_SERVO_1A, 500, 2400);
    servo1B.attach(PIN_SERVO_1B, 500, 2400);
    probeZ0.attach(PIN_PROBE_Z0, 500, 2400);
    probeZ1.attach(PIN_PROBE_Z1, 500, 2400);

    // Initial home positions (90 degrees, probes retracted)
    raiseProbes();
    moveServosSmooth(90.0, 90.0, 90.0, 90.0, 300);

    // Flash LED 3 times on boot
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); delay(60);
        digitalWrite(PIN_LED, LOW); delay(60);
    }

    // Announce ready state on serial port
    Serial.println();
    Serial.println(F("======================================================"));
    Serial.println(F("[ESP32] FPTester Dual 5-Bar Flying Probe Controller"));
    Serial.println(F("[ESP32] Firmware: v1.2.0 | Baud: 115200 | Status: READY"));
    Serial.println(F("[ESP32] Servos: Arm0(18,19) Arm1(21,22) ProbesZ(23,25)"));
    Serial.println(F("[ESP32] Waiting for test route commands from FPTester Web App..."));
    Serial.println(F("======================================================"));
}

void loop() {
    // Read incoming characters from Serial
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

// Simple JSON/Key-Value parser helper
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

    // Quick handshake / status commands
    if (cmd.equalsIgnoreCase("PING") || cmd.equalsIgnoreCase("?")) {
        Serial.println(F("{\"status\":\"pong\",\"device\":\"ESP32_FLYING_PROBE\",\"version\":\"1.2.0\"}"));
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
        moveServosSmooth(90.0, 90.0, 90.0, 90.0, 300);
        Serial.println(F("{\"status\":\"homed\",\"message\":\"Arms returned to 90 deg center datum.\"}"));
        return;
    }

    // FPTester Web App Test Route Command (JSON)
    // Format: {"msg_type":"run_test","job_id":101,"arms":[{"arm_id":0,"servo_a_deg":...},...]}
    if (cmd.indexOf("run_test") != -1 || cmd.indexOf("servo_a_deg") != -1 || cmd.startsWith("G0")) {
        int testId = extractInt(cmd, "test_id", 1);
        String net = extractString(cmd, "net", "NET_X");
        float expectedMin = extractFloat(cmd, "expected_min_v", 3.0);
        float expectedMax = extractFloat(cmd, "expected_max_v", 3.3);

        // Extract servo target angles
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

        // Support G0 parameters: G0 S0A=... S0B=... S1A=... S1B=...
        if (cmd.indexOf("S0A=") != -1) targetS0A = extractFloat(cmd, "S0A", targetS0A);
        if (cmd.indexOf("S0B=") != -1) targetS0B = extractFloat(cmd, "S0B", targetS0B);
        if (cmd.indexOf("S1A=") != -1) targetS1A = extractFloat(cmd, "S1A", targetS1A);
        if (cmd.indexOf("S1B=") != -1) targetS1B = extractFloat(cmd, "S1B", targetS1B);

        // Clamp to safe physical servo limits [15 deg to 165 deg]
        targetS0A = constrain(targetS0A, 15.0, 165.0);
        targetS0B = constrain(targetS0B, 15.0, 165.0);
        targetS1A = constrain(targetS1A, 15.0, 165.0);
        targetS1B = constrain(targetS1B, 15.0, 165.0);

        // Log to serial monitor
        Serial.print(F("[ESP32] Executing Test #"));
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

        // 1. Ensure probes are raised during XY planar travel
        raiseProbes();

        // 2. Move 5-bar linkage servos smoothly to target pad positions
        moveServosSmooth(targetS0A, targetS0B, targetS1A, targetS1B, 180);

        // 3. Lower probe needles onto target copper pads
        lowerProbes();
        delay(40); // Settle contact

        // 4. Inject 3.3V pulse on TX probe and measure ADC on RX probe
        digitalWrite(PIN_TX_SIGNAL, HIGH);
        delay(10);
        float measuredV = readProbeVoltage();
        int rawADC = analogRead(PIN_RX_ADC);
        digitalWrite(PIN_TX_SIGNAL, LOW);

        // 5. Retract probes after measurement
        raiseProbes();

        // Determine PASS / FAIL verdict
        String verdict = (measuredV >= expectedMin && measuredV <= expectedMax + 0.2) ? "PASS" : "FAIL";

        Serial.print(F("[ESP32] Measurement Result: "));
        Serial.print(measuredV, 2);
        Serial.print(F("V [ADC: "));
        Serial.print(rawADC);
        Serial.print(F("] -> Verdict: "));
        Serial.println(verdict);

        // Send JSON result back to FPTester App
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

    // Default unrecognized command fallback
    Serial.print(F("[ESP32] Command received: "));
    Serial.println(cmd);
}

void moveServosSmooth(float t0a, float t0b, float t1a, float t1b, int durationMs) {
    int steps = max(10, durationMs / 10);
    float start0a = currentS0A, start0b = currentS0B;
    float start1a = currentS1A, start1b = currentS1B;

    for (int i = 1; i <= steps; i++) {
        float factor = (float)i / steps;
        // Cosine easing for smooth deceleration at destination
        float ease = (1.0 - cos(factor * PI)) / 2.0;

        float a0a = start0a + (t0a - start0a) * ease;
        float a0b = start0b + (t0b - start0b) * ease;
        float a1a = start1a + (t1a - start1a) * ease;
        float a1b = start1b + (t1b - start1b) * ease;

        servo0A.write((int)round(a0a));
        servo0B.write((int)round(a0b));
        servo1A.write((int)round(a1a));
        servo1B.write((int)round(a1b));
        delay(durationMs / steps);
    }

    currentS0A = t0a;
    currentS0B = t0b;
    currentS1A = t1a;
    currentS1B = t1b;
}

void lowerProbes() {
    probeZ0.write(PROBE_DOWN_ANGLE);
    probeZ1.write(PROBE_DOWN_ANGLE);
    delay(60);
}

void raiseProbes() {
    probeZ0.write(PROBE_UP_ANGLE);
    probeZ1.write(PROBE_UP_ANGLE);
    delay(40);
}

float readProbeVoltage() {
    // Average 10 ADC samples for noise immunity
    long sum = 0;
    for (int i = 0; i < 10; i++) {
        sum += analogRead(PIN_RX_ADC);
        delayMicroseconds(50);
    }
    float raw = (float)sum / 10.0;
    float voltage = (raw / 4095.0) * 3.3;
    return voltage;
}
