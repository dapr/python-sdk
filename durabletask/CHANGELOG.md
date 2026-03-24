# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.3.0

### New

- Added `ConcurrencyOptions` class for fine-grained concurrency control with separate limits for activities and orchestrations. The thread pool worker count can also be configured.

### Fixed

- Fixed an issue where a worker could not recover after its connection was interrupted or severed

## v0.2.1

### New

- Added `set_custom_status` orchestrator API ([#31](https://github.com/microsoft/durabletask-python/pull/31)) - contributed by [@famarting](https://github.com/famarting)
- Added `purge_orchestration` client API ([#34](https://github.com/microsoft/durabletask-python/pull/34)) - contributed by [@famarting](https://github.com/famarting)

### Changes

- Protos are compiled with gRPC 1.62.3 / protobuf 3.25.X instead of the latest release. This ensures compatibility with a wider range of grpcio versions for better compatibility with other packages / libraries ([#36](https://github.com/microsoft/durabletask-python/pull/36)) - by [@berndverst](https://github.com/berndverst)
- Http and grpc protocols and their secure variants are stripped from the host name parameter if provided. Secure mode is enabled if the protocol provided is https or grpcs ([#38](https://github.com/microsoft/durabletask-python/pull/38) - by [@berndverst)(https://github.com/berndverst)
- Improve ProtoGen by downloading proto file directly instead of using submodule ([#39](https://github.com/microsoft/durabletask-python/pull/39) - by [@berndverst](https://github.com/berndverst)

### Updates

- Updated `durabletask-protobuf` submodule reference to latest

## v0.1.1a1

### New

- Add recursive flag in terminate_orchestration to support cascade terminate ([#27](https://github.com/microsoft/durabletask-python/pull/27)) - contributed by [@shivamkm07](https://github.com/shivamkm07)

## v0.1.0

### New

- Retry policies for activities and sub-orchestrations ([#11](https://github.com/microsoft/durabletask-python/pull/11)) - contributed by [@DeepanshuA](https://github.com/DeepanshuA)

### Fixed

- Fix try/except in orchestrator functions not being handled correctly ([#21](https://github.com/microsoft/durabletask-python/pull/21)) - by [@cgillum](https://github.com/cgillum)
- Updated `durabletask-protobuf` submodule reference to latest distributed tracing commit - by [@cgillum](https://github.com/cgillum)

## v0.1.0a5

### New

- Adds support for secure channels ([#18](https://github.com/microsoft/durabletask-python/pull/18)) - contributed by [@elena-kolevska](https://github.com/elena-kolevska)

### Fixed

- Fix zero argument values sent to activities as None ([#13](https://github.com/microsoft/durabletask-python/pull/13)) - contributed by [@DeepanshuA](https://github.com/DeepanshuA)

## v0.1.0a3

### New

- Add gRPC metadata option ([#16](https://github.com/microsoft/durabletask-python/pull/16)) - contributed by [@DeepanshuA](https://github.com/DeepanshuA)

### Changes

- Removed Python 3.7 support due to EOL ([#14](https://github.com/microsoft/durabletask-python/pull/14)) - contributed by [@berndverst](https://github.com/berndverst)

## v0.1.0a2

### New

- Continue-as-new ([#9](https://github.com/microsoft/durabletask-python/pull/9))
- Support for Python 3.7+ ([#10](https://github.com/microsoft/durabletask-python/pull/10)) - contributed by [@DeepanshuA](https://github.com/DeepanshuA)

## v0.1.0a1

Initial release, which includes the following features:

- Orchestrations and activities
- Durable timers
- Sub-orchestrations
- Suspend, resume, and terminate client operations
