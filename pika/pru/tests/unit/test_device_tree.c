/**
 * Unit tests for device tree overlay
 * 
 * Tests the device tree overlay structure and configuration
 * Requirements: 8.1, 8.2, 8.3, 8.5
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* Test counter */
static int tests_passed = 0;
static int tests_failed = 0;

/* Test helper macros */
#define TEST(name) \
    printf("Running test: %s\n", #name); \
    test_##name()

#define ASSERT_TRUE(condition, msg) \
    do { \
        if (condition) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s\n", msg); \
        } \
    } while(0)

#define ASSERT_EQ(actual, expected, msg) \
    do { \
        if ((actual) == (expected)) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s (expected %d, got %d)\n", msg, \
                   (int)(expected), (int)(actual)); \
        } \
    } while(0)

/* Helper function to read file content */
static char* read_file(const char* filename) {
    FILE* fp = fopen(filename, "r");
    if (!fp) {
        return NULL;
    }
    
    /* Get file size */
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    /* Allocate buffer and read */
    char* content = (char*)malloc(size + 1);
    if (!content) {
        fclose(fp);
        return NULL;
    }
    
    fread(content, 1, size, fp);
    content[size] = '\0';
    fclose(fp);
    
    return content;
}

/* Helper function to count occurrences of a string */
static int count_occurrences(const char* haystack, const char* needle) {
    int count = 0;
    const char* pos = haystack;
    
    while ((pos = strstr(pos, needle)) != NULL) {
        count++;
        pos += strlen(needle);
    }
    
    return count;
}

/* Helper function to check if string contains substring */
static int contains(const char* haystack, const char* needle) {
    return strstr(haystack, needle) != NULL;
}

/**
 * Test that device tree file exists and is readable
 */
void test_file_exists(void) {
    FILE* fp = fopen("../../../overlays/ad7606-pru0.dts", "r");
    ASSERT_TRUE(fp != NULL, "Device tree file should exist and be readable");
    if (fp) fclose(fp);
}

/**
 * Test basic device tree structure
 * Requirement: 8.1, 8.2, 8.3
 */
void test_basic_structure(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for required DTS declarations */
    ASSERT_TRUE(contains(content, "/dts-v1/;"), 
                "Should contain /dts-v1/ declaration");
    ASSERT_TRUE(contains(content, "/plugin/;"), 
                "Should contain /plugin/ declaration");
    
    /* Check for compatible string */
    ASSERT_TRUE(contains(content, "compatible") && 
                contains(content, "beaglebone"), 
                "Should contain BeagleBone compatible string");
    
    /* Check for part number */
    ASSERT_TRUE(contains(content, "part-number") && 
                contains(content, "BB-PRU0-AD7606"), 
                "Should contain correct part number");
    
    /* Check for version */
    ASSERT_TRUE(contains(content, "version"), 
                "Should contain version field");
    
    /* Check for exclusive-use declaration */
    ASSERT_TRUE(contains(content, "exclusive-use"), 
                "Should contain exclusive-use declaration");
    
    free(content);
}

/**
 * Test HDMI disable fragment
 * Requirement: 8.1 - Disable HDMI to free pins
 */
void test_hdmi_disable(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for fragment@0 (HDMI disable) */
    ASSERT_TRUE(contains(content, "fragment@0"), 
                "Should contain fragment@0");
    
    /* Check for lcdc target */
    ASSERT_TRUE(contains(content, "target = <&lcdc>"), 
                "Should target lcdc (LCD controller)");
    
    /* Check for status = "disabled" */
    ASSERT_TRUE(contains(content, "status = \"disabled\""), 
                "Should disable HDMI/LCD controller");
    
    free(content);
}

/**
 * Test PRU pin multiplexing configuration
 * Requirement: 8.2, 8.3 - Configure PRU pins
 */
void test_pin_multiplexing(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for fragment@1 (pin mux) */
    ASSERT_TRUE(contains(content, "fragment@1"), 
                "Should contain fragment@1 for pin multiplexing");
    
    /* Check for am33xx_pinmux target */
    ASSERT_TRUE(contains(content, "target = <&am33xx_pinmux>"), 
                "Should target am33xx_pinmux");
    
    /* Check for pinmux node */
    ASSERT_TRUE(contains(content, "pru0_ad7606_pins") || 
                contains(content, "pinmux_pru0"), 
                "Should contain PRU0 pinmux node");
    
    /* Check for pinctrl-single,pins */
    ASSERT_TRUE(contains(content, "pinctrl-single,pins"), 
                "Should contain pinctrl-single,pins property");
    
    free(content);
}

/**
 * Test CONVST output pin configuration
 * Requirement: 8.4 - Configure P9.31 as PRU0 R30.0 output
 */
void test_convst_pin(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for P9.31 in exclusive-use */
    ASSERT_TRUE(contains(content, "P9.31"), 
                "Should declare P9.31 in exclusive-use");
    
    /* Check for CONVST pin configuration (0x190 = P9.31 offset) */
    ASSERT_TRUE(contains(content, "0x190"), 
                "Should configure P9.31 register offset (0x190)");
    
    /* Check for output mode (0x05 = mode 5, output) */
    ASSERT_TRUE(contains(content, "0x05"), 
                "Should configure output mode (0x05)");
    
    /* Check for CONVST comment/documentation */
    ASSERT_TRUE(contains(content, "CONVST") || contains(content, "convst"), 
                "Should document CONVST signal");
    
    /* Check for R30.0 documentation */
    ASSERT_TRUE(contains(content, "R30.0") || contains(content, "r30_0"), 
                "Should document PRU0 R30.0 mapping");
    
    free(content);
}

/**
 * Test BUSY input pin configuration
 * Requirement: 8.4 - Configure P9.29 as PRU0 R31.0 input
 */
void test_busy_pin(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for P9.29 in exclusive-use */
    ASSERT_TRUE(contains(content, "P9.29"), 
                "Should declare P9.29 in exclusive-use");
    
    /* Check for BUSY pin configuration (0x194 = P9.29 offset) */
    ASSERT_TRUE(contains(content, "0x194"), 
                "Should configure P9.29 register offset (0x194)");
    
    /* Check for input mode (0x26 = mode 6, input with pull-down) */
    ASSERT_TRUE(contains(content, "0x26"), 
                "Should configure input mode (0x26)");
    
    /* Check for BUSY comment/documentation */
    ASSERT_TRUE(contains(content, "BUSY") || contains(content, "busy"), 
                "Should document BUSY signal");
    
    /* Check for R31.0 documentation */
    ASSERT_TRUE(contains(content, "R31.0") || contains(content, "r31_0"), 
                "Should document PRU0 R31.0 mapping");
    
    free(content);
}

/**
 * Test data pin configurations
 * Requirement: 8.5 - Configure data lines D0-D15 as inputs
 */
void test_data_pins(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for data pin declarations in exclusive-use */
    ASSERT_TRUE(contains(content, "P9.27"), "Should declare P9.27 (D0)");
    ASSERT_TRUE(contains(content, "P9.25"), "Should declare P9.25 (D1)");
    ASSERT_TRUE(contains(content, "P8.45"), "Should declare P8.45 (D8)");
    ASSERT_TRUE(contains(content, "P8.40"), "Should declare P8.40 (D15)");
    
    /* Count input mode configurations (0x26) - should have at least 17 (BUSY + 16 data) */
    int input_count = count_occurrences(content, "0x26");
    ASSERT_TRUE(input_count >= 17, 
                "Should have at least 17 input pin configurations (BUSY + D0-D15)");
    
    /* Check for data bit documentation */
    ASSERT_TRUE(contains(content, "D0") || contains(content, "Data bit 0"), 
                "Should document D0 data bit");
    ASSERT_TRUE(contains(content, "D15") || contains(content, "Data bit 15"), 
                "Should document D15 data bit");
    
    /* Check for R31 input documentation */
    ASSERT_TRUE(contains(content, "R31.1") || contains(content, "r31_1"), 
                "Should document R31.1 for D0");
    ASSERT_TRUE(contains(content, "R31.16") || contains(content, "r31_16"), 
                "Should document R31.16 for D15");
    
    free(content);
}

/**
 * Test PRU subsystem enable fragment
 * Requirement: 8.3 - Enable PRU subsystem
 */
void test_pru_enable(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for fragment@2 (PRU enable) */
    ASSERT_TRUE(contains(content, "fragment@2"), 
                "Should contain fragment@2 for PRU enable");
    
    /* Check for pruss target */
    ASSERT_TRUE(contains(content, "target = <&pruss>"), 
                "Should target pruss (PRU subsystem)");
    
    /* Check for status = "okay" */
    ASSERT_TRUE(contains(content, "status = \"okay\""), 
                "Should enable PRU subsystem with status = okay");
    
    /* Check for pinctrl reference */
    ASSERT_TRUE(contains(content, "pinctrl-0"), 
                "Should reference pin configuration");
    ASSERT_TRUE(contains(content, "pinctrl-names"), 
                "Should have pinctrl-names property");
    
    free(content);
}

/**
 * Test pin-to-signal mapping documentation
 * Requirement: 8.5 - Document pin-to-signal mapping
 */
void test_pin_documentation(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Check for comprehensive pin mapping table/comments */
    ASSERT_TRUE(contains(content, "Pin Mapping") || 
                contains(content, "Signal") || 
                contains(content, "BBB Pin"), 
                "Should contain pin mapping documentation");
    
    /* Check for signal descriptions */
    ASSERT_TRUE(contains(content, "Convert") || contains(content, "trigger"), 
                "Should document CONVST function");
    ASSERT_TRUE(contains(content, "Conversion in progress") || 
                contains(content, "BUSY"), 
                "Should document BUSY function");
    
    /* Check for direction documentation */
    ASSERT_TRUE(contains(content, "Output") || contains(content, "output"), 
                "Should document output pins");
    ASSERT_TRUE(contains(content, "Input") || contains(content, "input"), 
                "Should document input pins");
    
    /* Check for PRU register documentation */
    ASSERT_TRUE(contains(content, "R30") && contains(content, "R31"), 
                "Should document PRU R30 and R31 registers");
    
    free(content);
}

/**
 * Test syntax correctness
 */
void test_syntax(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Count braces */
    int open_braces = count_occurrences(content, "{");
    int close_braces = count_occurrences(content, "}");
    ASSERT_EQ(open_braces, close_braces, 
              "Opening and closing braces should be balanced");
    
    /* Count angle brackets */
    int open_angles = count_occurrences(content, "<");
    int close_angles = count_occurrences(content, ">");
    ASSERT_EQ(open_angles, close_angles, 
              "Opening and closing angle brackets should be balanced");
    
    /* Check for required fragments */
    ASSERT_TRUE(contains(content, "fragment@0"), "Should have fragment@0");
    ASSERT_TRUE(contains(content, "fragment@1"), "Should have fragment@1");
    ASSERT_TRUE(contains(content, "fragment@2"), "Should have fragment@2");
    
    free(content);
}

/**
 * Test pin count
 */
void test_pin_count(void) {
    char* content = read_file("../../../overlays/ad7606-pru0.dts");
    ASSERT_TRUE(content != NULL, "Should be able to read device tree file");
    
    if (!content) return;
    
    /* Count pin configurations (0xNNN 0xNN pattern) */
    /* Should have 18 total: 1 output (CONVST) + 1 input (BUSY) + 16 inputs (D0-D15) */
    int pin_configs = 0;
    const char* pos = content;
    while ((pos = strstr(pos, "0x")) != NULL) {
        /* Check if this looks like a pin configuration line */
        if (pos > content && *(pos-1) != '/') {  /* Not in a comment */
            const char* next = strstr(pos + 1, "0x");
            if (next && (next - pos) < 20) {  /* Second hex value nearby */
                pin_configs++;
                pos = next + 1;
                continue;
            }
        }
        pos++;
    }
    
    /* We expect at least 18 pin configurations */
    ASSERT_TRUE(pin_configs >= 18, 
                "Should have at least 18 pin configurations");
    
    free(content);
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== Device Tree Overlay Unit Tests ===\n\n");
    
    TEST(file_exists);
    TEST(basic_structure);
    TEST(hdmi_disable);
    TEST(pin_multiplexing);
    TEST(convst_pin);
    TEST(busy_pin);
    TEST(data_pins);
    TEST(pru_enable);
    TEST(pin_documentation);
    TEST(syntax);
    TEST(pin_count);
    
    printf("\n=== Test Results ===\n");
    printf("Passed: %d\n", tests_passed);
    printf("Failed: %d\n", tests_failed);
    
    if (tests_failed == 0) {
        printf("\nAll tests PASSED!\n");
        return 0;
    } else {
        printf("\nSome tests FAILED!\n");
        return 1;
    }
}
