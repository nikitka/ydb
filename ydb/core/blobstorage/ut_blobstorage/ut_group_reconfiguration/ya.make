UNITTEST_FOR(ydb/core/blobstorage/ut_blobstorage)

FORK_SUBTESTS()

FORK_SUBTESTS()

SIZE(LARGE)

TAG(ya:fat)

SRCS(
    race.cpp
)

PEERDIR(
    ydb/core/blobstorage/ut_blobstorage/lib
)

IF (SANITIZER_TYPE)
    REQUIREMENTS(ram:32)
ENDIF()

END()
