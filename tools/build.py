#!/usr/bin/env python3
"""Build the local OpenBOR libretro sources without network access.

SPDX-License-Identifier: BSD-3-Clause
Copyright (c) 2026 retrodiv <retrodiv@proton.me>
"""
import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from state_layout import write_bss_script

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "src"
CORE = "anybor_libretro"
BUILD_ROOT = Path(os.path.abspath(os.path.expanduser(
    os.environ.get("OBOR_BUILD_ROOT", str(HERE / ".build")))))
JOBS = max(1, int(os.environ.get("NUMPROC", os.environ.get("JOBS", min(4, os.cpu_count() or 4)))))
FIXED_ELF_IMAGE_BASE = "0x600000000000"
FIXED_PE_IMAGE_BASE = "0x240f10000"


def uses_fixed_elf_image(spec):
    """Return whether this target can preserve module pointers verbatim."""
    return spec["plat"] == "linux" and not spec.get("android")


def uses_fixed_pe_image(spec):
    """Return whether this target uses a stable Windows DLL image address."""
    return spec["plat"] == "windows"


def uses_macho(spec):
    """Return whether this target produces a Mach-O image."""
    return spec["plat"] == "darwin"


def arch_flags(spec):
    """Per-architecture flags a Darwin build must pass to clang and to ld.

    Darwin has no -march-style target selection: the architecture and the
    deployment floor travel as separate flags and both the compiler and the
    linker driver must see them.  libretro's macOS runners drive cross builds
    through LIBRETRO_APPLE_PLATFORM / LIBRETRO_APPLE_ISYSROOT (see the
    osx-arm64.yml CI template) and export MACOSX_DEPLOYMENT_TARGET, so those
    take precedence over the target defaults recorded here.
    """
    if not uses_macho(spec):
        return []
    apple_target = os.environ.get('LIBRETRO_APPLE_PLATFORM')
    flags = []
    if apple_target:
        flags += ['-target', apple_target]
        sysroot = os.environ.get('LIBRETRO_APPLE_ISYSROOT')
        if sysroot:
            flags += ['-isysroot', sysroot]
    else:
        flags += ['-arch', spec['arch']]
    floor = os.environ.get('MACOSX_DEPLOYMENT_TARGET') or spec.get('min_version', '11.0')
    flags.append('-mmacosx-version-min=' + floor)
    return flags


def android_ndk_root():
    for var in ("ANDROID_NDK", "ANDROID_NDK_HOME", "ANDROID_NDK_ROOT", "NDK_ROOT"):
        if os.environ.get(var):
            return os.environ[var]
    return ""


NDK_BIN = android_ndk_root() + "/toolchains/llvm/prebuilt/linux-x86_64/bin/"

TARGETS = {
    "linux-x86_64": {
        "cc": "gcc",
        "cxx": "g++",
        "strip": "strip",
        "plat": "linux",
        "ext": ".so",
        "glue_link": ["-shared", "-fPIC"],
        "static_pngz": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": None,
    },
    "windows-x86_64": {
        "cc": "x86_64-w64-mingw32-gcc",
        "cxx": "x86_64-w64-mingw32-g++",
        "strip": "x86_64-w64-mingw32-strip",
        "plat": "windows",
        "ext": ".dll",
        "glue_link": ["-shared", "-static", "-Wl,--no-insert-timestamp"],
        "static_pngz": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": "x86_64-w64-mingw32",
    },
    "linux-aarch64": {
        "cc": "aarch64-linux-gnu-gcc",
        "cxx": "aarch64-linux-gnu-g++",
        "strip": "aarch64-linux-gnu-strip",
        "plat": "linux",
        "ext": ".so",
        "glue_link": ["-shared", "-fPIC"],
        "static_pngz": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": "aarch64-linux-gnu",
    },
    "recalbox-aarch64": {
        "cc": "aarch64-linux-gnu-gcc",
        "cxx": "aarch64-linux-gnu-g++",
        "strip": "aarch64-linux-gnu-strip",
        "plat": "linux",
        "ext": ".so",
        "glue_link": ["-shared", "-fPIC"],
        "static_pngz": True,
        "deps_target": "linux-aarch64",
        "recalbox": True,
        "max_glibc": "2.38",
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": "aarch64-linux-gnu",
    },
    "android-arm64": {
        "cc": NDK_BIN + "aarch64-linux-android24-clang",
        "cxx": NDK_BIN + "aarch64-linux-android24-clang++",
        "strip": NDK_BIN + "llvm-strip",
        "plat": "linux",
        "ext": ".so",
        "glue_link": ["-shared", "-fPIC"],
        "static_pngz": True,
        "android": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": "aarch64-linux-android",
    },
    # Mach-O targets.  Apple's linker is the only one that implements the
    # relocatable-link step the engine build depends on, so these build on
    # macOS (macos-15-intel / macos-15 runners) or through an equally
    # complete cross toolchain such as OSXCross with a licensed SDK.
    "macos-x86_64": {
        "cc": "clang",
        "cxx": "clang++",
        "strip": "strip",
        "plat": "darwin",
        "ext": ".dylib",
        "arch": "x86_64",
        "min_version": "10.13",
        "glue_link": ["-dynamiclib"],
        "static_pngz": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": None,
    },
    "macos-arm64": {
        "cc": "clang",
        "cxx": "clang++",
        "strip": "strip",
        "plat": "darwin",
        "ext": ".dylib",
        "arch": "arm64",
        "min_version": "11.0",
        "glue_link": ["-dynamiclib"],
        "static_pngz": True,
        "dep_builds": ["zlib", "libpng", "libogg", "libvorbis", "libvpx"],
        "configure_host": None,
    },
}


def run(cmd, cwd=None, env=None):
    # Compiler variables may contain a launcher such as "ccache gcc".
    if not Path(str(cmd[0])).exists() and " " in str(cmd[0]):
        cmd = shlex.split(str(cmd[0])) + list(cmd[1:])
    print("+ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd is not None else None, env=env, check=True)


def load_pin():
    return json.loads((SRC / "pin.json").read_text(encoding="utf-8"))


def deps_prefix(target):
    return BUILD_ROOT / "deps" / target


def sha256_file(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_pe_metadata(path):
    """Zero volatile timestamp/checksum fields inserted by GNU strip."""
    path = Path(path)
    data = bytearray(path.read_bytes())
    if len(data) < 0x40 or data[:2] != b"MZ":
        sys.exit('not a PE image: {0}'.format(path))
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if pe + 24 + 68 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        sys.exit('invalid PE header: {0}'.format(path))
    struct.pack_into("<I", data, pe + 8, 0)
    struct.pack_into("<I", data, pe + 24 + 64, 0)
    path.write_bytes(data)


def tool_identity(command):
    parts = shlex.split(command)
    exe = shutil.which(parts[0])
    if not exe:
        sys.exit('required compiler not found: {0}'.format(command))
    r = subprocess.run(parts + ["--version"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    return [str(Path(exe).resolve()),
            (r.stdout or r.stderr or "unknown").splitlines()[0]]


def deps_fingerprint(target):
    spec, pin = TARGETS[target], load_pin()
    dep_names = set(spec["dep_builds"])
    payload = {
        "schema": 4,
        "target": target,
        "install_prefix": str(deps_prefix(target)),
        "cc": tool_identity(spec["cc"]),
        "cxx": tool_identity(spec["cxx"]),
        "builder": sha256_file(Path(__file__)),
        "environment": {k: os.environ.get(k, "") for k in
                        ("CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "NASM", "SOURCE_DATE_EPOCH")},
        "host": spec.get("configure_host"),
        "assembler": tool_identity(os.environ.get("NASM", "nasm")) if spec["arch"] == "x86_64" else None,
        "cflags": " ".join(["-O2", "-fPIC", "-fstack-protector-strong"] + arch_flags(spec)),
        "deps": {n: pin["deps"][n] for n in sorted(dep_names)},
        "sources": {str(p.relative_to(SRC)): sha256_file(p)
                    for n in sorted(dep_names) for p in sorted((SRC / "deps" / n).rglob("*"))
                    if p.is_file()},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_dep(target, name, fingerprint):
    spec, pin = TARGETS[target], load_pin()
    prefix = deps_prefix(target)
    marker = prefix / (".built-" + name)
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == fingerprint:
        return
    root = BUILD_ROOT / "dep-src" / (target + "-" + name)
    if root.exists():
        shutil.rmtree(str(root))
    source = SRC / "deps" / name
    if not source.is_dir():
        sys.exit("Missing bundled dependency source: " + str(source))
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source), str(root))
    # The bundled release-generated configure/Makefile.in files are the
    # build inputs. A Git checkout gives configure.ac/Makefile.am fresh
    # mtimes, which must not trigger regeneration of the bundled scripts.
    # Normalize only the disposable copy, including all m4 dependencies.
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(str(path), (epoch, epoch))
            if (path.name in {"configure", "install-sh", "depcomp", "missing", "compile"}
                    or path.suffix in {".sh", ".pl"}):
                path.chmod(path.stat().st_mode | 0o700)
    src = root
    env = os.environ.copy()
    env["CC"] = spec["cc"]
    env["CXX"] = spec["cxx"]
    env["AR"] = spec["ar"]
    env["RANLIB"] = spec["ranlib"]
    # Darwin builds carry the architecture and deployment floor on every
    # compile and link: the checked-in dependency sources are shared between
    # the two Mach-O targets.
    darwin = " ".join(arch_flags(spec))
    env["CFLAGS"] = "-O2 -fPIC -fstack-protector-strong " + darwin + " " + os.environ.get("CFLAGS", "")
    if darwin:
        env["LDFLAGS"] = darwin + " " + os.environ.get("LDFLAGS", "")
    host = (["--host=" + spec["configure_host"]]
            if spec.get("configure_host") else [])
    if name == "zlib":
        if spec["plat"] == "windows":
            run(["make", "-f", "win32/Makefile.gcc",
                 "CC=" + spec["cc"], "AR=" + spec["ar"], "RC=" + os.environ.get("WINDRES", spec["cc"][:-3] + "windres"),
                 "CFLAGS=" + env["CFLAGS"],
                 "BINARY_PATH=" + str(prefix / "bin"),
                 "INCLUDE_PATH=" + str(prefix / "include"),
                 "LIBRARY_PATH=" + str(prefix / "lib"), "install"], src, env)
        else:
            run(["sh", "./configure", "--prefix=" + str(prefix), "--static"], src, env)
            run(["make", "-s", "install"], src, env)
    elif name == "libpng":
        run(["sh", "./configure", "--prefix=" + str(prefix), "--disable-shared",
             "--enable-static", "--disable-tests", "--disable-tools", "CPPFLAGS=-I" + str(prefix / "include"),
             "LDFLAGS=-L" + str(prefix / "lib") + ((" " + darwin) if darwin else ""), *host], src, env)
        run(["make", "-s", "-j" + str(JOBS), "install"], src, env)
    elif name == "libogg":
        run(["sh", "./configure", "--prefix=" + str(prefix), "--disable-shared",
             "--enable-static", *host], src, env)
        for directory in ("src", "include"):
            run(["make", "-s", "-C", directory, "-j" + str(JOBS), "install"], src, env)
    elif name == "libvorbis":
        run(["sh", "./configure", "--prefix=" + str(prefix), "--disable-shared",
             "--enable-static", "--disable-dependency-tracking", "--with-ogg=" + str(prefix),
             "CPPFLAGS=-I" + str(prefix / "include"),
             "LDFLAGS=-L" + str(prefix / "lib") + ((" " + darwin) if darwin else ""), *host], src, env)
        for directory in ("lib", "include"):
            run(["make", "-s", "-C", directory, "-j" + str(JOBS), "install"], src, env)
    elif name == "libvpx":
        if spec["plat"] == "windows": vpx_target = "x86_64-win64-gcc"
        elif spec.get("android"): vpx_target = "arm64-android-gcc"
        elif uses_macho(spec): vpx_target = ("arm64-darwin-gcc" if spec["arch"] == "arm64"
                                             else "x86_64-darwin-gcc")
        elif spec["arch"] == "aarch64": vpx_target = "arm64-linux-gcc"
        else: vpx_target = "x86_64-linux-gcc"
        cfg = ["sh", "./configure", "--prefix=" + str(prefix),
               "--target=" + vpx_target, "--enable-static", "--disable-shared",
               "--enable-pic", "--enable-vp8-decoder", "--enable-vp9-decoder",
               "--disable-vp8-encoder", "--disable-vp9-encoder",
               "--disable-examples", "--disable-tools", "--disable-docs",
               "--disable-unit-tests", "--disable-libyuv", "--disable-webm-io"]
        if spec["arch"] == "x86_64":
            env["AS"] = os.environ.get("NASM", "nasm")
            if not shutil.which(env["AS"]):
                sys.exit("NASM is required for the x86-64 decoder (set NASM or install nasm).")
        if spec.get("android"):
            ndk = str(Path(spec["strip"]).parent)
            env.update(CXX=spec["cxx"], LD=spec["cxx"],
                       AR=ndk + "/llvm-ar", AS=spec["cc"], STRIP=spec["strip"])
        else:
            env["LD"] = spec["cc"]
            env["STRIP"] = spec["strip"]
        print("+ " + " ".join(cfg), flush=True)
        subprocess.run(cfg, cwd=str(src), env=env, check=True)
        print("+ make install", flush=True)
        subprocess.run(["make", "-s", "-j" + str(JOBS),
                        "install"], cwd=str(src), env=env, check=True)
    marker.write_text(fingerprint + "\n", encoding="utf-8")


def ensure_deps(target):
    prefix = deps_prefix(target)
    fingerprint = deps_fingerprint(target)
    stamp = prefix / ".obor-deps-fingerprint"
    if prefix.exists() and (not stamp.exists() or
                            stamp.read_text(encoding="utf-8").strip() != fingerprint):
        shutil.rmtree(str(prefix))
    prefix.mkdir(parents=True, exist_ok=True)
    stamp.write_text(fingerprint + "\n", encoding="utf-8")
    for name in TARGETS[target]["dep_builds"]:
        build_dep(target, name, fingerprint)


def enforce_glibc_ceiling(binary, ceiling):
    import re
    r = subprocess.run(["readelf", "--version-info", str(binary)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    versions = [(int(a), int(b))
                for a, b in re.findall(r"GLIBC_(\d+)\.(\d+)", r.stdout)]
    newest = max(versions, default=(0, 0))
    limit = tuple(int(x) for x in ceiling.split(".", 1))
    if newest > limit:
        sys.exit('{0}: needs GLIBC_{1}.{2}, but Recalbox permits at most GLIBC_{3}'.format(binary, newest[0], newest[1], ceiling))
    print('Recalbox ABI gate: GLIBC_{0}.{1} <= GLIBC_{2}'.format(newest[0], newest[1], ceiling))


def uniquify_refptr_sections(obj, build, spec):
    objdump = spec["objdump"]
    objcopy = spec["objcopy"]
    r = subprocess.run([objdump, "-h", str(obj)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, check=True)
    args = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) > 2 and parts[1].startswith(".rdata$.refptr."):
            sym = parts[1][len(".rdata$.refptr."):]
            args += ["--rename-section",
                     '{0}=.rdata$rp{1}.{2}'.format(parts[1], build, sym)]
    if args:
        run([objcopy] + args + [str(obj)])


def localize_android_engine(objdir, build, spec):
    # LLD's relocatable links retain COMMON symbols even with -d. Localizing
    # COMMON with llvm-objcopy turns those tentative definitions into absolute
    # symbols. Keep them global until the final allocation and give each engine
    # a private namespace; the final export map hides them from the frontend.
    nm = str(Path(spec["objdump"]).parent / "llvm-nm")
    whole = objdir / "whole.o"
    symbols = subprocess.check_output([nm, "--format=posix", str(whole)], universal_newlines=True)
    common = sorted(line.split()[0] for line in symbols.splitlines()
                    if len(line.split()) >= 2 and line.split()[1] == "C")
    abi = (objdir / "keep.txt").read_text(encoding="utf-8").split()
    keep = objdir / "android-keep.txt"
    keep.write_text("\n".join(abi + common) + "\n", encoding="utf-8")
    kept = objdir / "android-kept.o"
    run([spec["objcopy"], "--keep-global-symbols=" + str(keep), str(whole), str(kept)])
    renames = ["--redefine-sym=" + name + "=" + name + "_" + build for name in abi]
    renames += ["--redefine-sym=" + name + "=obor_common_" + build + "_" + name for name in common]
    run([spec["objcopy"], "--remove-section=.drectve"] + renames +
        [str(kept), str(objdir / ("obor_engine_" + build + ".o"))])


def build_engine(target, eng, spec, outdir, check_only=False):
    build = eng["build"]
    tree = SRC / "engines" / build
    if not (tree / "Makefile.libretro").exists():
        sys.exit('missing generated engine source: {0}'.format(tree))
    dep = deps_prefix(target)
    if not dep.exists():
        sys.exit('missing prepared dependencies for {0}: {1}'.format(target, dep))
    objdir = BUILD_ROOT / "objs" / target / build
    # Make's timestamps alone cannot detect compiler/flag changes or a source
    # regenerated with an older mtime. Fingerprint the actual local inputs.
    engine_flags = os.environ.get("CFLAGS", "")
    if uses_macho(spec):
        # Darwin has no fixed image address: dyld slides and rebases every
        # loaded image, so save states take the rebasing path the Android
        # target uses instead of the fixed-ELF/fixed-PE one.  The architecture
        # and deployment floor must reach the compiler and the partial link.
        engine_flags += " " + " ".join(arch_flags(spec))
    elif uses_fixed_elf_image(spec):
        engine_flags += " -DOBOR_FIXED_ELF_IMAGE=1"
    elif uses_fixed_pe_image(spec):
        engine_flags += " -DOBOR_FIXED_PE_IMAGE=1"
    payload = {"spec": spec, "deps": (dep / ".obor-deps-fingerprint").read_text(encoding="utf-8"),
               "flags": engine_flags,
               "files": {str(p.relative_to(SRC)): sha256_file(p)
                         for root in (tree, SRC / "port/libretro")
                         for p in sorted(root.rglob("*")) if p.is_file()}}
    if uses_macho(spec):
        payload["macho_rewrite"] = sha256_file(HERE / "tools/macho_rewrite.py")
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    stamp = objdir / ".inputs-sha256"
    if check_only:
        if not stamp.exists() or stamp.read_text(encoding="utf-8") != fingerprint or not (outdir / ("obor_engine_" + build + ".o")).is_file():
            sys.exit("Engine inputs changed or objects are missing; run a full make before glue.")
        return
    if objdir.exists() and (not stamp.exists() or stamp.read_text(encoding="utf-8") != fingerprint):
        shutil.rmtree(str(objdir))
    objdir.mkdir(parents=True, exist_ok=True)
    mk = [
        "make", "-f", "Makefile.libretro", "-j" + str(JOBS),
        "partial",
        'BUILD_NUM={0}'.format(build),
        'PLATFORM={0}'.format(spec['plat']),
        'CC={0}'.format(spec['cc']),
        'DEPS_PREFIX={0}'.format(dep),
        'OBJDIR={0}'.format(objdir),
        'PORT_ROOT={0}'.format(SRC / 'port' / 'libretro'),
        'STATIC_PNGZ={0}'.format(1 if spec.get('static_pngz') else 0),
        'EXTRA_EXCLUDE={0}'.format(' '.join(eng.get('exclude', []))),
        "LDR=" + spec["ld"] + (
            " -map " + str(outdir / ("engine-" + build + ".map")) if uses_macho(spec)
            else " -Map=" + str(outdir / ("engine-" + build + ".map"))),
        "OBJCOPY=" + spec["objcopy"],
        "PYTHON=" + sys.executable,
        "DARWIN_ARCH=" + spec.get("arch", ""),
        "DARWIN_MINVER=" + (os.environ.get("MACOSX_DEPLOYMENT_TARGET")
                            or spec.get("min_version", "11.0")),
        "USER_CFLAGS=" + engine_flags,
    ]
    run(mk, cwd=tree)
    obj = objdir / 'obor_engine_{0}.o'.format(build)
    if not obj.exists():
        sys.exit('engine object not produced: {0}'.format(obj))
    if spec.get("android"):
        localize_android_engine(objdir, build, spec)
    if spec["plat"] == "windows":
        uniquify_refptr_sections(obj, build, spec)
    shutil.copy2(str(obj), str(outdir / obj.name))
    stamp.write_text(fingerprint, encoding="utf-8")


def build_glue(target, spec, outdir):
    pin = load_pin()
    core = pin.get("core_basename", CORE)
    engines = [outdir / 'obor_engine_{0}.o'.format(e['build']) for e in pin["engines"]]
    for obj in engines:
        if not obj.exists():
            sys.exit('missing {0}'.format(obj))

    third = SRC / "third_party"
    # engines/miniz are built one-section-per-function so the final link's
    # --gc-sections drops everything unreachable from the exported retro_*
    # API. ELF targets only: on PE the partial-link localize step breaks
    # the COMDAT association of per-function .pdata/.xdata (nothing gets
    # collected) and -fdata-sections turns .bss into file-backed .data.
    gc_cflags = (["-ffunction-sections", "-fdata-sections"]
                 if spec["plat"] == "linux" else [])
    gc_ldflags = (["-Wl,--gc-sections"] if spec["plat"] == "linux" else
                  ["-Wl,-dead_strip"] if uses_macho(spec) else [])
    miniz_o = outdir / "miniz.o"
    run([spec["cc"], "-O2", "-fPIC", "-fvisibility=hidden",
         *arch_flags(spec),
         "-fstack-protector-strong", *gc_cflags,
         "-ffile-prefix-map=" + str(HERE) + "=.",
         "-c", third / "miniz.c", "-o", miniz_o])

    compat_objs = []
    for name in ("obor_transform_vm", "obor_transform_source"):
        obj = outdir / (name + ".o")
        run([spec["cc"], "-O2", "-std=c99", "-fPIC", "-fvisibility=hidden",
             *arch_flags(spec),
             "-fstack-protector-strong", *gc_cflags,
             "-ffile-prefix-map=" + str(HERE) + "=.",
             "-c", SRC / "glue" / (name + ".c"), "-o", obj])
        compat_objs.append(obj)
    compat_flags = []
    if spec["plat"] == "linux" and not spec.get("android"):
        compat_o = outdir / "glibc_compat_math.o"
        run([spec["cc"], "-O2", "-fPIC", "-fvisibility=hidden",
             "-fstack-protector-strong", *gc_cflags,
             "-ffile-prefix-map=" + str(HERE) + "=.",
             "-c",
             SRC / "compat" / "glibc_compat_math.c", "-o", compat_o])
        compat_objs.append(compat_o)
        compat_flags += ["-Wl,--wrap=acosf", "-Wl,--wrap=asinf",
                         "-Wl,--wrap=sqrtf"]

    glue_defs = ['-DOBOR_PLATFORM="{0}"'.format(target)]
    if spec.get("recalbox"):
        glue_defs += ["-DOBOR_NO_INPUT_DESCRIPTORS=1", "-DOBOR_NO_PADMAP=1",
                      "-DOBOR_NO_OSD_MESSAGES=1"]

    out = outdir / '{0}{1}'.format(core, spec['ext'])
    bss_script = outdir / "state-bss.ld"
    if not uses_macho(spec):
        write_bss_script(bss_script, engines, pe=spec["plat"] == "windows")
    cmd = [
        spec["cxx"], "-O2", "-std=c++11", "-fvisibility=hidden",
        "-fstack-protector-strong",
        *gc_cflags,
        *glue_defs,
        "-ffile-prefix-map=" + str(HERE) + "=.",
        "-I", SRC / "glue", "-I", third,
        SRC / "glue" / "libretro.cpp",
        miniz_o,
        *compat_objs,
        *engines,
        "-o", out,
        *gc_ldflags,
        *spec["glue_link"],
        *compat_flags,
    ]
    if uses_macho(spec):
        # Mach-O: no linker script (the per-engine regions come from the
        # partials), no version script; the exported ABI is an explicit list
        # because Mach-O has no wildcard version scripts.  The image stays
        # position independent and dyld is free to slide it, exactly like the
        # ELF targets that reserve their own address.
        # Glue uses C++ lifetime syntax but no C++ library, RTTI or exceptions.
        # Do not introduce a libc++ dependency into the libSystem-only core.
        cmd += arch_flags(spec) + ["-fno-exceptions", "-fno-rtti", "-nostdlib++"]
        cmd += ["-Wl,-exported_symbols_list," + str(SRC / "glue" / "exports.macho"),
                "-Wl,-install_name,@rpath/" + core + ".dylib",
                "-Wl,-no_uuid",  # reproducible: no random LC_UUID
                "-lm"]
    else:
        cmd += ["-Wl,-T," + str(bss_script)]
    if spec["plat"] == "linux":
        cmd += ["-Wl,-z,relro", "-Wl,-z,now",
                '-Wl,--version-script={0}'.format(SRC / 'glue' / 'exports.map'),
                "-ldl", "-lm"]
        if spec.get("android"):
            cmd += ["-static-libstdc++", "-Wl,-z,max-page-size=16384",
                    "-Wl,-z,common-page-size=16384"]
        else:
            # Savestates contain engine function and static-data pointers.
            # Loading this ET_DYN image at one reserved address keeps those
            # pointers valid across frontend processes and avoids guessing
            # which 64-bit words in large game buffers happen to look like
            # pointers.  The arena lives separately at 0x2a00000000.
            cmd += ["-Wl,-Ttext-segment=" + FIXED_ELF_IMAGE_BASE, "-lpthread"]
        if not spec.get("static_pngz"):
            cmd += ["-lpng", "-lz"]
    elif spec["plat"] == "windows":
        # PE savestates carry the same module pointers as ELF states.  Disable
        # loader randomization and request the same otherwise-unused high base;
        # retain relocations so an actual collision fails safely at state load.
        cmd += ["-lwinmm", "-lpsapi", "-Wl,-Bstatic", "-lpthread",
                "-Wl,--image-base," + FIXED_PE_IMAGE_BASE,
                "-Wl,--disable-dynamicbase"]
    cmd += (["-Wl,-map," + str(outdir / "link.map")] if uses_macho(spec)
            else ["-Wl,-Map=" + str(outdir / "link.map")])
    cmd += shlex.split(os.environ.get("CXXFLAGS", ""))
    cmd += shlex.split(os.environ.get("LDFLAGS", ""))
    run(cmd)
    if spec.get("max_glibc"):
        enforce_glibc_ceiling(out, spec["max_glibc"])
    if spec.get("android"):
        import re
        headers = subprocess.check_output([spec["objdump"], "-p", str(out)], universal_newlines=True)
        alignment = [int(x) for x in re.findall(r"LOAD[^\n]*align 2\*\*([0-9]+)", headers)]
        if not alignment or min(alignment) < 14:
            sys.exit("Android ELF load segments must be aligned to at least 16 KiB.")
    shutil.copy2(str(out), str(out.with_suffix(out.suffix + ".sym")))
    # Apple's strip has no --strip-unneeded; -x drops exactly the local
    # symbols the export list already hides from the frontend.
    run([spec["strip"], "-x" if uses_macho(spec) else "--strip-unneeded", out])
    if spec["plat"] == "windows":
        normalize_pe_metadata(out)
    shutil.copy2(str(out), str(HERE / out.name))
    # Keep the unstripped artifact under .build only.  The repository root is
    # the normal release surface and must not acquire large debug artifacts as
    # a side effect of an ordinary build.
    sym = HERE / (out.name + ".sym")
    if sym.exists():
        sym.unlink()


def configure_target(requested, build_platform):
    """Honor the tools supplied by libretro runners, including native ARM64."""
    inferred_native = False
    if requested == "auto":
        if build_platform in ("win", "win64", "windows"):
            requested = "windows-x86_64"
        elif build_platform in ("android", "android-arm64"):
            requested = "android-arm64"
        elif build_platform in ("aarch64", "linux-aarch64"):
            requested = "linux-aarch64"
        else:
            inferred_native = True
            command = shlex.split(os.environ.get("CC", "gcc"))
            machine = subprocess.check_output(command + ["-dumpmachine"], universal_newlines=True)
            if "apple" in machine or "darwin" in machine:
                # Native macOS: which of the two Mach-O targets this is comes
                # from the compiler triple, not from the platform argument,
                # because libretro's runner passes platform=osx for both.
                requested = ("macos-arm64" if machine.startswith(("aarch64", "arm64"))
                             else "macos-x86_64")
            else:
                requested = "linux-aarch64" if machine.startswith(("aarch64", "arm64")) else "linux-x86_64"
    spec = dict(TARGETS[requested])
    if spec.get("android") and not android_ndk_root():
        sys.exit("Set ANDROID_NDK or NDK_ROOT to an installed Android NDK.")
    if inferred_native and not uses_macho(spec):
        spec.update(cc="gcc", cxx="g++")
    spec["cc"] = os.environ.get("CC", spec["cc"])
    cxx_default = spec["cc"][:-3] + "g++" if spec["cc"].endswith("gcc") else spec["cxx"]
    spec["cxx"] = os.environ.get("CXX", cxx_default)
    cc = shlex.split(spec["cc"])[-1]
    prefix = cc[:-3] if cc.endswith("gcc") else ""
    ndk = str(Path(spec["cc"]).parent) + "/"
    for key, executable in (("ar", "ar"), ("ranlib", "ranlib"), ("strip", "strip"),
                            ("ld", "ld"), ("objcopy", "objcopy"), ("objdump", "objdump")):
        default = prefix + executable
        if spec.get("android"):
            default = ndk + ("ld.lld" if key == "ld" else "llvm-" + executable)
        spec[key] = os.environ.get(key.upper(), default)
    spec["arch"] = spec.get("arch") or (
        "aarch64" if "aarch64" in requested or spec.get("android") else "x86_64")
    if spec.get("android"):
        spec["ext"] = "_android.so"
    if spec.get("configure_host"):
        spec["configure_host"] = subprocess.check_output(
            shlex.split(spec["cc"]) + ["-dumpmachine"], universal_newlines=True).strip()
    TARGETS[requested] = spec
    return requested, spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["auto"] + list(TARGETS), default="auto")
    ap.add_argument("--platform", default=os.environ.get("platform", "unix"))
    ap.add_argument("--glue-only", action="store_true")
    args = ap.parse_args()
    epoch = load_pin()["source_date_epoch"]
    os.environ.setdefault("SOURCE_DATE_EPOCH", str(epoch))
    args.target, spec = configure_target(args.target, args.platform)
    outdir = BUILD_ROOT / "dist" / args.target
    outdir.mkdir(parents=True, exist_ok=True)
    import release
    source_snapshot = release.source_files()
    ensure_deps(args.target)
    for eng in load_pin()["engines"]:
        build_engine(args.target, eng, spec, outdir, check_only=args.glue_only)
    build_glue(args.target, spec, outdir)
    release.record_build(args.target, spec, outdir, source_snapshot)


if __name__ == "__main__":
    main()
