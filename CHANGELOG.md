# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - Unreleased

> **Placeholder:** release notes for the next tag after [`adwize-v0.1.1`](https://github.com/Adwize/adwize-oss/releases/tag/adwize-v0.1.1).
> Not tagged yet — Senior Developer will create `adwize-v0.1.2` after this merges.
> Expected release day: **2026-10-11** (or update the date when tagging).

### Security

- Redact webhook URLs in logs, `NotificationLog`, test-notification API responses, and MCP `test_webhook` messages (keep `scheme://host`, replace path/query/fragment with `/***`); delivery still uses the original URL ([#29](https://github.com/Adwize/adwize-oss/pull/29))
- Mask API key and database password input during `adwize setup`; the setup-complete summary shows only the last four characters of the API key (or `not set`) ([#34](https://github.com/Adwize/adwize-oss/pull/34))
- Run API and worker container images as non-root user `app` (UID/GID `10001`) ([#38](https://github.com/Adwize/adwize-oss/pull/38))
- Add a root `.dockerignore` so host `.env`, `.venv`, caches, and similar files are not copied into image layers ([#40](https://github.com/Adwize/adwize-oss/pull/40))
- Cap MCP `send_events` `count` to **1–100** and return a clear error outside that range ([#27](https://github.com/Adwize/adwize-oss/pull/27))
- Harden default Compose bindings to `127.0.0.1` for Postgres and the API, and drop `--reload` from the production compose command ([#19](https://github.com/Adwize/adwize-oss/pull/19))

### Added

- `SECURITY.md` with responsible-disclosure guidance for this OSS stack ([#20](https://github.com/Adwize/adwize-oss/pull/20))
- `docker-compose.dev.yml` for local hot-reload alongside the hardened production compose defaults ([#19](https://github.com/Adwize/adwize-oss/pull/19))
- Dependabot config plus issue and pull request templates ([#14](https://github.com/Adwize/adwize-oss/pull/14))
- README cross-link to adwize-audit ([#13](https://github.com/Adwize/adwize-oss/pull/13))

### Changed

- When an API key is set, `adwize setup` prints `ADWIZE_API_KEY` in the MCP config snippet alongside `ADWIZE_API_URL`; README MCP examples document the same ([#31](https://github.com/Adwize/adwize-oss/pull/31))
- Bump CI actions: `astral-sh/setup-uv` 4 → 7 ([#15](https://github.com/Adwize/adwize-oss/pull/15)), `actions/checkout` 4 → 7 ([#16](https://github.com/Adwize/adwize-oss/pull/16))

### Fixed

- Make `install.sh` safe under `curl | bash` by reading prompts from `/dev/tty` and defaulting to update when noninteractive ([#22](https://github.com/Adwize/adwize-oss/pull/22))
- Correct the CONTRIBUTING clone URL to `Adwize/adwize-oss` ([#8](https://github.com/Adwize/adwize-oss/pull/8))
- Install script and CLI README rendering fixes ([#6](https://github.com/Adwize/adwize-oss/pull/6), [#7](https://github.com/Adwize/adwize-oss/pull/7))

## [0.1.1] - 2026-05-14

Tagged as [`adwize-v0.1.1`](https://github.com/Adwize/adwize-oss/releases/tag/adwize-v0.1.1).

## [0.1.0] - 2026-05-14

Tagged as [`adwize-v0.1.0`](https://github.com/Adwize/adwize-oss/releases/tag/adwize-v0.1.0).

[0.1.2]: https://github.com/Adwize/adwize-oss/compare/adwize-v0.1.1...HEAD
[0.1.1]: https://github.com/Adwize/adwize-oss/compare/adwize-v0.1.0...adwize-v0.1.1
[0.1.0]: https://github.com/Adwize/adwize-oss/releases/tag/adwize-v0.1.0
