#pragma once

/**
 * @file tracer.h
 * @brief W3C Distributed Context Tracing (TraceContext) for C++17 Microservices.
 *
 * Implements W3C TraceContext specification (version 00):
 * Format: 00-{trace_id:32hex}-{span_id:16hex}-{flags:02hex}
 * Provides lightweight zero-overhead distributed context propagation and RAII Spans.
 */

#include <chrono>
#include <iomanip>
#include <map>
#include <memory>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace hams {
namespace tracing {

inline std::string generateRandomHex(size_t num_chars) {
    static thread_local std::mt19937_64 rng(
        static_cast<uint64_t>(std::chrono::high_resolution_clock::now().time_since_epoch().count())
    );
    static const char hex_digits[] = "0123456789abcdef";
    std::uniform_int_distribution<size_t> dist(0, 15);

    std::string result;
    result.reserve(num_chars);
    for (size_t i = 0; i < num_chars; ++i) {
        result.push_back(hex_digits[dist(rng)]);
    }
    return result;
}

struct TraceContext {
    std::string version{"00"};
    std::string trace_id;        // 32-char hex
    std::string span_id;         // 16-char hex
    std::string parent_span_id;  // 16-char hex (optional)
    bool sampled{true};

    std::string toTraceparent() const {
        return version + "-" + trace_id + "-" + span_id + (sampled ? "-01" : "-00");
    }

    static TraceContext createRoot(bool sampled = true) {
        TraceContext ctx;
        ctx.version = "00";
        ctx.trace_id = generateRandomHex(32);
        ctx.span_id = generateRandomHex(16);
        ctx.parent_span_id = "";
        ctx.sampled = sampled;
        return ctx;
    }

    TraceContext createChild() const {
        TraceContext child;
        child.version = version;
        child.trace_id = trace_id;
        child.span_id = generateRandomHex(16);
        child.parent_span_id = span_id;
        child.sampled = sampled;
        return child;
    }

    static std::optional<TraceContext> fromTraceparent(const std::string& header) {
        // Format: 00-{32}-{16}-{02} => total 55 characters
        if (header.size() != 55) {
            return std::nullopt;
        }
        if (header[2] != '-' || header[35] != '-' || header[52] != '-') {
            return std::nullopt;
        }

        std::string ver = header.substr(0, 2);
        std::string tid = header.substr(3, 32);
        std::string sid = header.substr(36, 16);
        std::string flags = header.substr(53, 2);

        // Check for all-zero invalid IDs
        if (tid == "00000000000000000000000000000000" || sid == "0000000000000000") {
            return std::nullopt;
        }

        TraceContext ctx;
        ctx.version = ver;
        ctx.trace_id = tid;
        ctx.span_id = sid;
        ctx.parent_span_id = "";
        ctx.sampled = (flags == "01");
        return ctx;
    }
};

class Span {
public:
    Span(const std::string& name, const TraceContext& context)
        : name_(name), context_(context), start_time_(std::chrono::steady_clock::now()), ended_(false) {}

    ~Span() {
        if (!ended_) {
            end();
        }
    }

    void setTag(const std::string& key, const std::string& value) {
        tags_[key] = value;
    }

    void end() {
        if (!ended_) {
            end_time_ = std::chrono::steady_clock::now();
            ended_ = true;
        }
    }

    double getDurationMs() const {
        auto end = ended_ ? end_time_ : std::chrono::steady_clock::now();
        auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(end - start_time_).count();
        return static_cast<double>(duration_us) / 1000.0;
    }

    const TraceContext& getContext() const { return context_; }
    const std::string& getName() const { return name_; }
    const std::map<std::string, std::string>& getTags() const { return tags_; }

    std::string toJson() const {
        std::ostringstream ss;
        ss << "{"
           << "\"name\":\"" << name_ << "\","
           << "\"trace_id\":\"" << context_.trace_id << "\","
           << "\"span_id\":\"" << context_.span_id << "\","
           << "\"parent_span_id\":\"" << context_.parent_span_id << "\","
           << "\"duration_ms\":" << std::fixed << std::setprecision(3) << getDurationMs() << ","
           << "\"traceparent\":\"" << context_.toTraceparent() << "\""
           << "}";
        return ss.str();
    }

private:
    std::string name_;
    TraceContext context_;
    std::chrono::steady_clock::time_point start_time_;
    std::chrono::steady_clock::time_point end_time_;
    std::map<std::string, std::string> tags_;
    bool ended_;
};

}  // namespace tracing
}  // namespace hams
