#include <gtest/gtest.h>
#include "tracer.h"

using namespace hams::tracing;

TEST(TracerTest, RootTraceContextCreation) {
    auto root = TraceContext::createRoot(true);
    EXPECT_EQ(root.version, "00");
    EXPECT_EQ(root.trace_id.size(), 32UL);
    EXPECT_EQ(root.span_id.size(), 16UL);
    EXPECT_TRUE(root.parent_span_id.empty());
    EXPECT_TRUE(root.sampled);

    std::string tp = root.toTraceparent();
    EXPECT_EQ(tp.size(), 55UL);
    EXPECT_EQ(tp.substr(0, 3), "00-");
    EXPECT_EQ(tp.substr(52, 3), "-01");
}

TEST(TracerTest, ChildSpanPropagation) {
    auto root = TraceContext::createRoot(true);
    auto child = root.createChild();

    EXPECT_EQ(child.version, "00");
    EXPECT_EQ(child.trace_id, root.trace_id);
    EXPECT_EQ(child.parent_span_id, root.span_id);
    EXPECT_NE(child.span_id, root.span_id);
    EXPECT_TRUE(child.sampled);
}

TEST(TracerTest, ParseW3CTraceparent) {
    std::string raw = "00-11112222333344445555666677778888-aaaabbbbccccdddd-01";
    auto parsed = TraceContext::fromTraceparent(raw);
    EXPECT_TRUE(parsed.has_value());
    EXPECT_EQ(parsed->trace_id, "11112222333344445555666677778888");
    EXPECT_EQ(parsed->span_id, "aaaabbbbccccdddd");
    EXPECT_TRUE(parsed->sampled);

    // Invalid all-zeros trace ID
    std::string invalid_zeros = "00-00000000000000000000000000000000-0000000000000000-01";
    auto invalid_res = TraceContext::fromTraceparent(invalid_zeros);
    EXPECT_FALSE(invalid_res.has_value());

    // Invalid length
    EXPECT_FALSE(TraceContext::fromTraceparent("short-invalid").has_value());
}

TEST(TracerTest, SpanTimingAndTags) {
    auto ctx = TraceContext::createRoot(true);
    Span span("compute_tensor_kernel", ctx);
    span.setTag("gpu.device", "cuda:0");
    span.setTag("batch.size", "64");

    // Simulate small computation
    volatile double dummy = 0.0;
    for (int i = 0; i < 10000; ++i) {
        dummy += i * 0.1;
    }
    (void)dummy;

    span.end();
    EXPECT_GE(span.getDurationMs(), 0.0);
    EXPECT_EQ(span.getName(), "compute_tensor_kernel");
    EXPECT_EQ(span.getTags().at("gpu.device"), "cuda:0");

    std::string json_repr = span.toJson();
    EXPECT_TRUE(json_repr.find("compute_tensor_kernel") != std::string::npos);
    EXPECT_TRUE(json_repr.find(ctx.trace_id) != std::string::npos);
}
