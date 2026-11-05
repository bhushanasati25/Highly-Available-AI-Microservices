#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <functional>
#include <cmath>

namespace testing {
    struct TestInfo {
        std::string suite;
        std::string name;
        std::function<void()> func;
    };

    inline std::vector<TestInfo>& get_tests() {
        static std::vector<TestInfo> tests;
        return tests;
    }

    inline int register_test(const std::string& suite, const std::string& name, std::function<void()> func) {
        get_tests().push_back({suite, name, func});
        return 0;
    }

    inline int& failures() {
        static int f = 0;
        return f;
    }

    inline int InitGoogleTest(int* argc, char** argv) {
        (void)argc;
        (void)argv;
        return 0;
    }

    inline int RUN_ALL_TESTS() {
        int passed = 0;
        int failed = 0;
        std::cout << "[==========] Running " << get_tests().size() << " tests.\n";
        for (const auto& t : get_tests()) {
            std::cout << "[ RUN      ] " << t.suite << "." << t.name << "\n";
            int before = failures();
            try {
                t.func();
            } catch (const std::exception& e) {
                failures()++;
                std::cout << "[  FAILED  ] Exception: " << e.what() << "\n";
            }
            if (failures() == before) {
                std::cout << "[       OK ] " << t.suite << "." << t.name << "\n";
                passed++;
            } else {
                std::cout << "[  FAILED  ] " << t.suite << "." << t.name << "\n";
                failed++;
            }
        }
        std::cout << "[==========] " << get_tests().size() << " tests ran. "
                  << passed << " passed, " << failed << " failed.\n";
        return failed > 0 ? 1 : 0;
    }
}

#define TEST(suite, name) \
    void _test_##suite##_##name(); \
    static int _reg_##suite##_##name = ::testing::register_test(#suite, #name, _test_##suite##_##name); \
    void _test_##suite##_##name()

#define EXPECT_TRUE(cond) do { if (!(cond)) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_TRUE(" #cond ")\n"; } } while(0)
#define EXPECT_FALSE(cond) do { if (cond) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_FALSE(" #cond ")\n"; } } while(0)
#define EXPECT_EQ(a, b) do { if (!((a) == (b))) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_EQ(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_NE(a, b) do { if ((a) == (b)) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_NE(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_NEAR(a, b, eps) do { if (std::abs((a) - (b)) > (eps)) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_NEAR(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_DOUBLE_EQ(a, b) EXPECT_NEAR(a, b, 1e-6)
#define EXPECT_FLOAT_EQ(a, b) EXPECT_NEAR(a, b, 1e-5f)
#define EXPECT_GT(a, b) do { if (!((a) > (b))) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_GT(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_LT(a, b) do { if (!((a) < (b))) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_LT(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_GE(a, b) do { if (!((a) >= (b))) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_GE(" #a ", " #b ")\n"; } } while(0)
#define EXPECT_LE(a, b) do { if (!((a) <= (b))) { ::testing::failures()++; std::cerr << "  FAILED: EXPECT_LE(" #a ", " #b ")\n"; } } while(0)
#define ASSERT_TRUE(cond) EXPECT_TRUE(cond)
#define ASSERT_EQ(a, b) EXPECT_EQ(a, b)

#ifndef NO_GTEST_MAIN
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return ::testing::RUN_ALL_TESTS();
}
#endif
