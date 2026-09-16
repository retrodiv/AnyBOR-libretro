/* SPDX-License-Identifier: BSD-3-Clause
 * Copyright (c) 2026 retrodiv <retrodiv@proton.me> */
#ifndef OBOR_STORAGE_H
#define OBOR_STORAGE_H

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>
#include "obor_zip_path.h"
#if defined(_WIN32)
#include <windows.h>
#include <direct.h>
#else
#include <unistd.h>
#endif

/* Process/session state, preserved across engine resets and state restores. */
struct obor_storage_session {
    char root[1200];
    char used[4][1600]; /* ZIP, its staging directory, and prepared PACK */
    unsigned count;
    bool clear_on_unload;
};
static obor_storage_session g_storage;

static bool obor_storage_join(char *out, size_t cap, const char *root, const char *leaf)
{
    int n = snprintf(out, cap, "%s/%s", root, leaf);
    if (n >= 0 && (size_t)n < cap) return true;
    out[0] = 0;
    return false;
}

/* Never descend through a symlink or a Windows junction/reparse point. */
static bool obor_storage_directory(const char *path)
{
#if defined(_WIN32)
    DWORD a = GetFileAttributesA(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY) &&
           !(a & FILE_ATTRIBUTE_REPARSE_POINT);
#else
    struct stat s;
    return lstat(path, &s) == 0 && S_ISDIR(s.st_mode);
#endif
}

static bool obor_storage_remove(const char *path, unsigned depth = 0)
{
    if (depth > 64) return false;
    if (!obor_storage_directory(path)) {
#if defined(_WIN32)
        DWORD a = GetFileAttributesA(path);
        if (a == INVALID_FILE_ATTRIBUTES)
            return GetLastError() == ERROR_FILE_NOT_FOUND || GetLastError() == ERROR_PATH_NOT_FOUND;
        if (a & FILE_ATTRIBUTE_DIRECTORY) return RemoveDirectoryA(path) != 0;
#endif
        return remove(path) == 0 || errno == ENOENT;
    }
    DIR *dir = opendir(path);
    if (!dir) return false;
    bool ok = true;
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char child[4096];
        if (!obor_storage_join(child, sizeof(child), path, entry->d_name) ||
            !obor_storage_remove(child, depth + 1)) ok = false;
    }
    closedir(dir);
#if defined(_WIN32)
    if (_rmdir(path)) ok = false;
#else
    if (rmdir(path)) ok = false;
#endif
    return ok;
}

static bool obor_storage_begin(const char *save_dir, bool clear_all, bool clear_current)
{
    memset(&g_storage, 0, sizeof(g_storage));
    g_storage.clear_on_unload = clear_current;
    if (!obor_storage_join(g_storage.root, sizeof(g_storage.root), save_dir, "AnyBOR-cache"))
        return false;
    return !clear_all || obor_storage_remove(g_storage.root);
}

/* Called only with loader-generated paths, before writing or reusing them. */
static bool obor_storage_track(const char *path)
{
    if (!g_storage.root[0]) return true; /* standalone preparation tools */
    size_t n = strlen(g_storage.root);
    if (strncmp(path, g_storage.root, n) || path[n] != '/') return false;
    for (unsigned i = 0; i < g_storage.count; ++i)
        if (!strcmp(g_storage.used[i], path)) return true;
    if (g_storage.count >= 4 || strlen(path) >= sizeof(g_storage.used[0])) return false;
    strcpy(g_storage.used[g_storage.count++], path);
    return true;
}

static bool obor_storage_finish(void)
{
    bool ok = true;
    if (g_storage.clear_on_unload && obor_storage_directory(g_storage.root)) {
        for (unsigned i = 0; i < g_storage.count; ++i) {
            char parent[1600];
            strcpy(parent, g_storage.used[i]);
            char *slash = strrchr(parent, '/');
            if (!slash) { ok = false; continue; }
            *slash = 0;
            if (!obor_storage_directory(parent)) continue;
            if (!obor_storage_remove(g_storage.used[i])) ok = false;
        }
    }
    memset(&g_storage, 0, sizeof(g_storage));
    return ok;
}

/* Both cache producers share this root; refuse redirected cache namespaces. */
static bool obor_storage_parent(const char *save_dir, const char *kind, char *out, size_t cap)
{
    char root[1200];
    if (!obor_storage_join(root, sizeof(root), save_dir, "AnyBOR-cache")) return false;
    mkdir_p(root);
    if (!obor_storage_directory(root) || !obor_storage_join(out, cap, root, kind)) return false;
    mkdir_p(out);
    return obor_storage_directory(out);
}

/* Derive the namespace from the original frontend content name, before ZIP
 * extraction or preparation changes its path. Reject ambiguous/unsafe names. */
static bool obor_storage_game_directory(const char *save_dir, const char *content,
                                        char *out, size_t cap)
{
    char path[4096];
    if (strlen(content) >= sizeof(path)) return false;
    strcpy(path, content);
    for (char *p = path; *p; ++p) if (*p == '\\') *p = '/';
    char *name = strrchr(path, '/');
    name = name ? name + 1 : path;
    size_t n = strlen(name);
    if (!strcasecmp(name, "models.txt")) {
        if (name == path) return false;
        name[-1] = 0;
        char *data = strrchr(path, '/');
        if (!data || strcasecmp(data + 1, "data")) return false;
        *data = 0;
        name = strrchr(path, '/');
        name = name ? name + 1 : path;
    } else {
        if (n <= 4 || (strcasecmp(name + n - 4, ".pak") &&
            strcasecmp(name + n - 4, ".spk") && strcasecmp(name + n - 4, ".zip"))) return false;
        name[n - 4] = 0;
    }
    char safe[4096];
    if (!obor_zip_component(name, strlen(name)) ||
        !obor_zip_safe_name(name, safe, sizeof(safe))) return false;
    char base[1400];
    if (!obor_storage_join(base, sizeof(base), save_dir, "AnyBOR")) return false;
    mkdir_p(base);
    if (!obor_storage_directory(base) || !obor_storage_join(out, cap, base, name)) return false;
    /* A missing game folder is fine; an existing link must not redirect
     * cleanup or game writes outside this game's namespace. */
#if defined(_WIN32)
    DWORD a = GetFileAttributesA(out);
    return a == INVALID_FILE_ATTRIBUTES || obor_storage_directory(out);
#else
    struct stat st;
    return lstat(out, &st) != 0 ? errno == ENOENT : S_ISDIR(st.st_mode);
#endif
}
#endif
