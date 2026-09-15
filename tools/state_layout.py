"""Keep each engine's zero-initialized globals in a bounded linker region.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import json
import re


def write_bss_script(path, engines, *, pe=False):
    """Augment the default ELF/PE linker script without folding partials.

    No KEEP: normal dead-section collection still applies. ELF NOLOAD retains
    zero-fill storage instead of adding the multi-MiB BSS to the core file.
    PE must inherit the input BSS type and align the output section itself:
    NOLOAD produces an invalid raw size/type, and aligning only its contents
    leaves the section RVA unaligned. Wine accepts images Windows rejects.
    COMMON matters for LLD partials, which retain tentative definitions.
    """
    section = ".obss ALIGN(__section_alignment__)" if pe else ".obss (NOLOAD)"
    lines = ["SECTIONS {", "  " + section + " : { "]
    for obj in engines:
        match = re.fullmatch(r"obor_engine_(\d+)\.o", obj.name)
        if not match:
            raise ValueError("Invalid engine object name: " + obj.name)
        build = match.group(1)
        lines += ["    . = ALIGN(64);",
                  "    __obor_bss_begin_" + build + " = .;",
                  "    " + json.dumps(str(obj), ensure_ascii=False) + "(.bss .bss.* COMMON)",
                  "    __obor_bss_end_" + build + " = .;"]
    lines += ["  }", "} INSERT BEFORE .bss;", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
