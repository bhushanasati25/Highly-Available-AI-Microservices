#pragma once

#include <iostream>
#include <sstream>
#include <string>
#include <chrono>
#include <iomanip>
#include <mutex>

namespace spdlog {

namespace level {
    enum level_enum {
        trace = 0,
        debug = 1,
        info = 2,
        warn = 3,
        err = 4,
        critical = 5,
        off = 6
    };
}

inline level::level_enum& current_log_level() {
    static level::level_enum lvl = level::info;
    return lvl;
}

inline void set_level(level::level_enum lvl) {
    current_log_level() = lvl;
}

namespace detail {
    inline std::mutex& log_mutex() {
        static std::mutex mtx;
        return mtx;
    }

    inline std::string get_timestamp() {
        auto now = std::chrono::system_clock::now();
        auto in_time_t = std::chrono::system_clock::to_time_t(now);
        auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
        std::stringstream ss;
        ss << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %H:%M:%S");
        ss << '.' << std::setfill('0') << std::setw(3) << ms.count();
        return ss.str();
    }

    inline void format_to_stream(std::ostringstream& oss, const std::string& fmt) {
        oss << fmt;
    }

    template<typename T, typename... Args>
    void format_to_stream(std::ostringstream& oss, const std::string& fmt, T&& value, Args&&... args) {
        size_t pos = fmt.find("{}");
        if (pos != std::string::npos) {
            oss << fmt.substr(0, pos);
            oss << std::forward<T>(value);
            format_to_stream(oss, fmt.substr(pos + 2), std::forward<Args>(args)...);
        } else {
            oss << fmt;
        }
    }

    template<typename... Args>
    void log_msg(level::level_enum lvl, const char* level_name, const std::string& fmt, Args&&... args) {
        if (lvl < current_log_level()) return;
        std::lock_guard<std::mutex> lock(log_mutex());
        std::ostringstream oss;
        format_to_stream(oss, fmt, std::forward<Args>(args)...);
        std::ostream& out = (lvl >= level::err) ? std::cerr : std::cout;
        out << "[" << get_timestamp() << "] [" << level_name << "] " << oss.str() << "\n";
    }
} // namespace detail

template<typename... Args>
inline void debug(const std::string& fmt, Args&&... args) {
    detail::log_msg(level::debug, "debug", fmt, std::forward<Args>(args)...);
}

template<typename... Args>
inline void info(const std::string& fmt, Args&&... args) {
    detail::log_msg(level::info, "info", fmt, std::forward<Args>(args)...);
}

template<typename... Args>
inline void warn(const std::string& fmt, Args&&... args) {
    detail::log_msg(level::warn, "warn", fmt, std::forward<Args>(args)...);
}

template<typename... Args>
inline void error(const std::string& fmt, Args&&... args) {
    detail::log_msg(level::err, "error", fmt, std::forward<Args>(args)...);
}

template<typename... Args>
inline void critical(const std::string& fmt, Args&&... args) {
    detail::log_msg(level::critical, "critical", fmt, std::forward<Args>(args)...);
}

} // namespace spdlog
