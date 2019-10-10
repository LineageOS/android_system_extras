#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "pm-wrapper.h"

#define PACKAGE_LIST_PATH "/data/system/packages.list"
#define PACKAGE_NAME_MAX_LEN (1 << 16)

/* reads a file, making sure it is terminated with \n \0 */
char* read_file(const char* fn) {
    struct stat st;
    char* data = NULL;

    int fd = open(fn, O_RDONLY);
    if (fd < 0) return data;

    if (fstat(fd, &st)) goto oops;

    data = static_cast<char*>(malloc(st.st_size + 2));
    if (!data) goto oops;

    if (read(fd, data, st.st_size) != st.st_size) goto oops;
    close(fd);
    data[st.st_size] = '\n';
    data[st.st_size + 1] = 0;
    return data;

oops:
    close(fd);
    if (data) free(data);
    return NULL;
}

/* Tries to resolve a package name from a uid via the packages list file.
 *
 * If there is no matching uid, it will return an empty string which can
 * be resolved by appops in some cases (i.e. apps with uid = 0, uid = AID_SHELL).
 *
 * Since packages may share UID, this function will return the first present
 * in packages.list.
 */
char* resolve_package_name(uid_t uid) {
    char* package_name = NULL;
    char* packages = read_file(PACKAGE_LIST_PATH);

    if (packages == NULL) {
        return NULL;
    }

    char* p = packages;
    while (*p) {
        char* line_end = strstr(p, "\n");
        if (line_end == NULL) break;

        char* token;
        char* pkgName = strtok_r(p, " ", &token);
        if (pkgName != NULL) {
            char* pkgUid = strtok_r(NULL, " ", &token);
            if (pkgUid != NULL) {
                char* endptr;
                errno = 0;
                uid_t pkgUidInt = strtoul(pkgUid, &endptr, 10);
                if ((errno == 0 && endptr != NULL && !(*endptr)) && pkgUidInt == uid) {
                    package_name = strdup(pkgName);
                    break;
                }
            }
        }
        p = ++line_end;
    }

    free(packages);
    return package_name;
}
