PY3TEST()

SIZE(MEDIUM)

PY_SRCS(
    run_tests/run_tests.py
)

TEST_SRCS(
    tpc_tests.py
)

DEPENDS(
    ydb/library/yql/tools/dqrun
    ydb/library/benchmarks/gen_queries
    ydb/library/benchmarks/runner/result_compare
    ydb/library/benchmarks/runner/runner

    ydb/library/yql/udfs/common/set
    ydb/library/yql/udfs/common/url_base
    ydb/library/yql/udfs/common/datetime2
    ydb/library/yql/udfs/common/re2
)

DATA(
    arcadia/ydb/library/yql/tools/dqrun/examples/fs.conf
    arcadia/ydb/library/benchmarks/runner/runner/test-gateways.conf
    contrib/tools/flame-graph
)

END()

RECURSE(
    run_tests
    runner
    result_convert
    result_compare
)
