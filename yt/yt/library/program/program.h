#pragma once

#include <yt/yt/core/misc/public.h>

#include <library/cpp/getopt/last_getopt.h>

#include <yt/yt/core/yson/string.h>

namespace NYT {

////////////////////////////////////////////////////////////////////////////////

class TProgram
{
public:
    TProgram();
    ~TProgram();

    TProgram(const TProgram&) = delete;
    TProgram(TProgram&&) = delete;

    // This call actually never returns;
    // |int| return type is just for the symmetry with |main|.
    [[noreturn]]
    int Run(int argc, const char** argv);

    //! Handles --version/--yt-version/--build [--yson] if they are present.
    void HandleVersionAndBuild();

    //! Nongracefully aborts the program.
    /*!
     *  Tries to flush logging messages.
     *  Aborts via |_exit| call.
     */
    [[noreturn]]
    static void Abort(int code) noexcept;

    //! A typed version of #Abort.
    template <class E>
        requires std::is_enum_v<E>
    [[noreturn]]
    static void Abort(E exitCode) noexcept;

protected:
    NLastGetopt::TOpts Opts_;
    TString Argv0_;
    bool PrintYTVersion_ = false;
    bool PrintVersion_ = false;
    bool PrintBuild_ = false;
    bool UseYson_ = false;

    virtual void DoRun() = 0;

    virtual void OnError(const TString& message) noexcept;

    virtual bool ShouldAbortOnHungShutdown() noexcept;

    void SetCrashOnError();

    //! Handler for --yt-version command argument.
    [[noreturn]]
    void PrintYTVersionAndExit();

    //! Handler for --build command argument.
    [[noreturn]]
    void PrintBuildAndExit();

    //! Handler for --version command argument.
    //! By default, --version and --yt-version work the same way,
    //! but some YT components (e.g. CHYT) can override it to provide its own version.
    [[noreturn]]
    virtual void PrintVersionAndExit();

    [[noreturn]]
    void Exit(int code) noexcept;

    //! A typed version of #Exit.
    template <class E>
        requires std::is_enum_v<E>
    [[noreturn]]
    void Exit(E exitCode) noexcept;

    const NLastGetopt::TOptsParseResult& GetOptsParseResult() const;

private:
    // Custom handler for option parsing errors.
    class TOptsParseResult;

    std::unique_ptr<TOptsParseResult> OptsParseResult_;
    bool CrashOnError_ = false;
};

////////////////////////////////////////////////////////////////////////////////

//! The simplest exception possible.
//! Here we refrain from using TErrorException, as it relies on proper configuration of singleton subsystems,
//! which might not be the case during startup.
class TProgramException
    : public std::exception
{
public:
    explicit TProgramException(TString what);

    const char* what() const noexcept override;

private:
    const TString What_;
};

////////////////////////////////////////////////////////////////////////////////

//! Helper for TOpt::StoreMappedResult to validate file paths for existence.
TString CheckPathExistsArgMapper(const TString& arg);

//! Helper for TOpt::StoreMappedResult to parse types with #FromString.
template <class T>
T FromStringArgMapper(TStringBuf arg);

//! Helper for TOpt::StoreMappedResult to parse enums.
template <class T>
T ParseEnumArgMapper(TStringBuf arg);

//! Helper for TOpt::StoreMappedResult to parse YSON strings.
NYson::TYsonString CheckYsonArgMapper(const TString& arg);

//! Drop privileges and save them if running with suid-bit.
void ConfigureUids();

void ConfigureCoverageOutput();

void ConfigureIgnoreSigpipe();

//! Intercepts standard crash signals (see signal_registry.h for full list) with a nice handler.
void ConfigureCrashHandler();

//! Intercepts SIGTERM and terminates the process immediately with zero exit code.
void ConfigureExitZeroOnSigterm();

////////////////////////////////////////////////////////////////////////////////

struct TAllocatorOptions
{
    std::optional<TDuration> SnapshotUpdatePeriod;
};

void ConfigureAllocator(const TAllocatorOptions& options = {});

////////////////////////////////////////////////////////////////////////////////

} // namespace NYT

#define PROGRAM_INL_H_
#include "program-inl.h"
#undef PROGRAM_INL_H_
