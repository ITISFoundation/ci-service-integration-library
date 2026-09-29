#!/bin/sh
#
# Shared computational-service entrypoint (T26me experiment, local branch only).
#
# - Executes *inside* of the container upon start as --user [default root]
# - The container *starts* as root but *runs* as non-root user [$SC_USER_NAME]
#
# Port of the approved Sleeper contract (github-osparc-services/services/sleeper,
# docker/custom/entrypoint.sh) per SPEC-COMP.md C15/C16/C17:
#   - full image traversal for files owned by the build-time service UID,
#     excluding pseudo-filesystems (/proc, /sys); declared mounts reconciled;
#   - bounded host-mount scope: never mutates unrelated host-mounted paths;
#   - pre-existing UID conflict removal (Ubuntu >= 24.04 ships uid 1000 users);
#   - exec gosu handoff (no extra shell, exit status is the application's).
# Consumer requirements (already satisfied by the ML runners' Dockerfiles):
#   - SC_USER_ID / SC_USER_NAME / INPUT_FOLDER / OUTPUT_FOLDER envs set;
#   - the service command reachable on PATH (e.g. service.cli in ENV PATH);
#   - gosu and fd-find (fdfind) installed in the image.
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

echo "$INFO" "Entrypoint for stage ${SC_BUILD_TARGET} ..."
echo "$INFO" "User :$(id "$(whoami)")"
echo "$INFO" "Workdir : $(pwd)"
echo "$INFO" "User : $(id "$SC_USER_NAME")"

# expect input/output folders to be mounted
stat "${INPUT_FOLDER}" >/dev/null 2>&1 ||
    (echo "$ERROR" "You must mount '${INPUT_FOLDER}' to deduce user and group ids" && exit 1)
stat "${OUTPUT_FOLDER}" >/dev/null 2>&1 ||
    (echo "$ERROR" "You must mount '${OUTPUT_FOLDER}' to deduce user and group ids" && exit 1)

# check input/output folders are owned by the same user and group
if [ "$(stat -c %u "${INPUT_FOLDER}")" -ne "$(stat -c %u "${OUTPUT_FOLDER}")" ]; then
    echo "$ERROR" "'${INPUT_FOLDER}' and '${OUTPUT_FOLDER}' have different user id's. not allowed" && exit 1
fi
if [ "$(stat -c %g "${INPUT_FOLDER}")" -ne "$(stat -c %g "${OUTPUT_FOLDER}")" ]; then
    echo "$ERROR" "'${INPUT_FOLDER}' and '${OUTPUT_FOLDER}' have different group id's. not allowed" && exit 1
fi

echo "$INFO" "setting correct user id/group id..."
HOST_USERID=$(stat --format=%u "${INPUT_FOLDER}")
HOST_GROUPID=$(stat --format=%g "${INPUT_FOLDER}")

if [ "$HOST_USERID" -ne 0 ]; then
    # some base images (e.g. Ubuntu >=24.04) ship a pre-existing user at uid 1000:
    # remove it first since it may also own the group we are about to resolve/reuse below
    CONFLICTING_USER=$(getent passwd "$HOST_USERID" | cut --delimiter=: --fields=1)
    if [ -n "$CONFLICTING_USER" ] && [ "$CONFLICTING_USER" != "$SC_USER_NAME" ]; then
        echo "$WARNING" "Removing pre-existing user '$CONFLICTING_USER' occupying uid $HOST_USERID..."
        deluser "$CONFLICTING_USER"
    fi
fi

CONT_GROUPNAME=$(getent group "${HOST_GROUPID}" | cut --delimiter=: --fields=1)
if [ "$HOST_USERID" -eq 0 ]; then
    echo "$WARNING" "Folder mounted owned by root user... adding $SC_USER_NAME to root..."
    adduser "$SC_USER_NAME" root
else
    echo "$INFO" "Folder mounted owned by user $HOST_USERID:$HOST_GROUPID-'$CONT_GROUPNAME'..."
    # take host's credentials in $SC_USER_NAME
    if [ -z "$CONT_GROUPNAME" ]; then
        echo "$INFO" "Creating new group my$SC_USER_NAME"
        CONT_GROUPNAME=my$SC_USER_NAME
        addgroup --gid "$HOST_GROUPID" "$CONT_GROUPNAME"
    else
        echo "$INFO" "group already exists"
    fi
    echo "$INFO" "adding $SC_USER_NAME to group $CONT_GROUPNAME..."
    adduser "$SC_USER_NAME" "$CONT_GROUPNAME"

    echo "$INFO" "changing $SC_USER_NAME:$SC_USER_NAME ($SC_USER_ID:$SC_USER_ID) to $SC_USER_NAME:$CONT_GROUPNAME ($HOST_USERID:$HOST_GROUPID)"
    usermod --uid "$HOST_USERID" --gid "$HOST_GROUPID" "$SC_USER_NAME"

    echo "$INFO" "Changing group properties of files around from $SC_USER_ID to group $CONT_GROUPNAME"
    fdfind --owner ":$SC_USER_ID" --exclude proc --exclude sys --exec-batch chgrp --no-dereference "$CONT_GROUPNAME" . '/'
    echo "$INFO" "Changing ownership properties of files around from $SC_USER_ID to group $SC_USER_ID"
    fdfind --owner "$SC_USER_ID:" --exclude proc --exclude sys --exec-batch chown --no-dereference "$SC_USER_NAME" . '/'
fi

echo "$INFO" "Starting $* ..."
echo "$INFO" "  $SC_USER_NAME rights    : $(id "$SC_USER_NAME")"
echo "$INFO" "  local dir : $(ls -al)"
echo "$INFO" "  input dir : $(ls -al "${INPUT_FOLDER}")"
echo "$INFO" "  output dir : $(ls -al "${OUTPUT_FOLDER}")"

exec gosu "$SC_USER_NAME" "$@"
