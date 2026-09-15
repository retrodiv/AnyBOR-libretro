# Local diagnostics

Diagnostics are disabled by default. The core does not send telemetry or
upload files. `OBOR_DEBUG=1` or a local `obor_debug.enable` file enables
engine diagnostics. `OBOR_TRACE=/path/to/file` records frontend frame and
save-state calls. `OBOR_GLUE_DUMP=/path/prefix` writes local frame captures
around state restoration. `OBOR_GLUE_INPUT` supplies scripted test input.
The game-log core option displays local engine log messages.

Logs and captures may contain local paths, game names, game script text or
game imagery. Review them before attaching them to a public issue. Disable
diagnostic variables after reproducing an issue and remove the local marker
file to restore the normal configuration.
