# Security and reporting

Report vulnerabilities privately using the repository host's private
reporting facility when available, or the contact on the maintainer's
profile. Include the core version, target, affected input path and a minimal
reproduction using content you can share. Do not publish credentials, game
PAKs or memory dumps in an issue.

OpenBOR content contains scripts executed by native engine code. Treat
games and save states as trusted software, and load them only from sources
you trust. Input validation and ZIP limits do not provide a sandbox for
hostile games or save states. Binary dependencies are built from the sources
included in this repository; upstream identities are in src/pin.json.

The core does not upload telemetry or diagnostic files. Optional local
diagnostics are enabled by `OBOR_DEBUG=1`, `OBOR_CRASHLOG=1`, or an
`obor_debug.enable` file beside the content. These write breadcrumbs and
crash information beside the content and can contain local paths. Additional
developer tracing is described in docs/DEBUGGING.md. Review and redact logs
before sharing them. The license dossier contains upstream attribution,
including addresses required by original notices; it contains no user data.

Maintainers receiving a report should keep personal data and non-public
reproductions private, request only the information needed to investigate,
and remove unnecessary attachments after resolving the issue.
