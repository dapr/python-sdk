#!/bin/sh
echo "Home: $HOME"

run_component() {
    component="$1"
    cd "$component" && mm.py -l README.md
}

extract_app_ids_from_readme() {
    readme="$1"
    awk '
    {
        line = $0
        while (match(line, /--app-id(=|[[:space:]]+)[A-Za-z0-9._-]+/)) {
            token = substr(line, RSTART, RLENGTH)
            sub(/^--app-id(=|[[:space:]]+)/, "", token)
            print token
            line = substr(line, RSTART + RLENGTH)
        }
    }' "$readme" | sort -u
}

extract_fixed_ports_from_readme() {
    readme="$1"
    awk '
    {
        line = $0
        while (match(line, /--(app-port|dapr-http-port|dapr-grpc-port)(=|[[:space:]]+)[0-9]+/)) {
            token = substr(line, RSTART, RLENGTH)
            kind = token
            sub(/=.*/, "", kind)
            sub(/[[:space:]].*/, "", kind)
            sub(/^--/, "", kind)

            port = token
            sub(/^.*(=|[[:space:]]+)/, "", port)
            print port "\t" kind
            line = substr(line, RSTART + RLENGTH)
        }
        line = $0
        while (match(line, /-p[[:space:]]*[0-9]+:[0-9]+/)) {
            token = substr(line, RSTART, RLENGTH)
            sub(/^-p[[:space:]]*/, "", token)
            split(token, parts, ":")
            print parts[1] "\tdocker-host-port"
            line = substr(line, RSTART + RLENGTH)
        }
    }' "$readme"
}

extract_container_names_from_readme() {
    readme="$1"
    awk '
    {
        line = $0
        while (match(line, /--name[[:space:]]+[A-Za-z0-9._-]+/)) {
            token = substr(line, RSTART, RLENGTH)
            sub(/^--name[[:space:]]+/, "", token)
            print token
            line = substr(line, RSTART + RLENGTH)
        }
        line = $0
        while (match(line, /docker[[:space:]]+(kill|stop|rm)[[:space:]]+[A-Za-z0-9._-]+/)) {
            token = substr(line, RSTART, RLENGTH)
            sub(/^docker[[:space:]]+(kill|stop|rm)[[:space:]]+/, "", token)
            print token
            line = substr(line, RSTART + RLENGTH)
        }
    }' "$readme" | sort -u
}

assert_no_duplicate_app_ids() {
    components="$1"
    tmpdir="$2"

    app_ids_file="$tmpdir/app_ids.tsv"
    duplicates_file="$tmpdir/duplicate_app_ids.txt"
    : >"$app_ids_file"

    for component in $components; do
        [ "$component" = ".." ] && continue
        readme="$component/README.md"
        [ -f "$readme" ] || continue

        extract_app_ids_from_readme "$readme" | while IFS= read -r app_id; do
            [ -n "$app_id" ] || continue
            printf '%s\t%s\n' "$app_id" "$component" >>"$app_ids_file"
        done
    done

    awk -F '\t' '
    {
        app = $1
        component = $2
        key = app SUBSEP component
        if (seen[key]++) {
            next
        }
        count[app]++
        components[app] = (components[app] == "" ? component : components[app] ", " component)
    }
    END {
        has_duplicates = 0
        for (app in count) {
            if (count[app] > 1) {
                has_duplicates = 1
                printf "  - %s: %s\n", app, components[app]
            }
        }
        exit has_duplicates ? 1 : 0
    }' "$app_ids_file" >"$duplicates_file"

    if [ $? -ne 0 ]; then
        echo "Duplicate Dapr app IDs detected across examples:"
        cat "$duplicates_file"
        return 1
    fi

    return 0
}

assert_no_duplicate_fixed_ports() {
    components="$1"
    tmpdir="$2"

    ports_file="$tmpdir/fixed_ports.tsv"
    duplicates_file="$tmpdir/duplicate_fixed_ports.txt"
    : >"$ports_file"

    for component in $components; do
        [ "$component" = ".." ] && continue
        readme="$component/README.md"
        [ -f "$readme" ] || continue

        extract_fixed_ports_from_readme "$readme" | while IFS="$(printf '\t')" read -r port kind; do
            [ -n "$port" ] || continue
            printf '%s\t%s\t%s\n' "$port" "$component" "$kind" >>"$ports_file"
        done
    done

    awk -F '\t' '
    {
        port = $1
        component = $2
        kind = $3
        key = port SUBSEP component
        if (seen[key]++) {
            next
        }
        count[port]++
        details[port] = (details[port] == "" ? component " (" kind ")" : details[port] ", " component " (" kind ")")
    }
    END {
        has_duplicates = 0
        for (port in count) {
            if (count[port] > 1) {
                has_duplicates = 1
                printf "  - %s: %s\n", port, details[port]
            }
        }
        exit has_duplicates ? 1 : 0
    }' "$ports_file" >"$duplicates_file"

    if [ $? -ne 0 ]; then
        echo "Duplicate fixed host ports detected across examples:"
        cat "$duplicates_file"
        return 1
    fi

    return 0
}

assert_no_duplicate_container_names() {
    components="$1"
    tmpdir="$2"

    names_file="$tmpdir/container_names.tsv"
    duplicates_file="$tmpdir/duplicate_container_names.txt"
    : >"$names_file"

    for component in $components; do
        [ "$component" = ".." ] && continue
        readme="$component/README.md"
        [ -f "$readme" ] || continue

        extract_container_names_from_readme "$readme" | while IFS= read -r name; do
            [ -n "$name" ] || continue
            printf '%s\t%s\n' "$name" "$component" >>"$names_file"
        done
    done

    awk -F '\t' '
    {
        name = $1
        component = $2
        key = name SUBSEP component
        if (seen[key]++) {
            next
        }
        count[name]++
        components[name] = (components[name] == "" ? component : components[name] ", " component)
    }
    END {
        has_duplicates = 0
        for (name in count) {
            if (count[name] > 1) {
                has_duplicates = 1
                printf "  - %s: %s\n", name, components[name]
            }
        }
        exit has_duplicates ? 1 : 0
    }' "$names_file" >"$duplicates_file"

    if [ $? -ne 0 ]; then
        echo "Duplicate container names detected across examples:"
        cat "$duplicates_file"
        return 1
    fi

    return 0
}

run_all_components_parallel() {
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/validate-all.XXXXXX")" || exit 1
    overall_status=0

    components=""
    for component in *; do
        if [ -d "$component" ] && [ -f "$component/README.md" ]; then
            components="$components $component"
        fi
    done
    components="$components .."

    if ! assert_no_duplicate_app_ids "$components" "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi

    if ! assert_no_duplicate_fixed_ports "$components" "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi

    if ! assert_no_duplicate_container_names "$components" "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi

    for component in $components; do
        safe_name="$(printf '%s' "$component" | tr '/.' '__')"
        (
            cd "$component" && mm.py -l README.md
        ) >"$tmpdir/$safe_name.log" 2>&1 &
        pid=$!
        printf '%s\n' "$pid" >"$tmpdir/$safe_name.pid"
    done

    for component in $components; do
        safe_name="$(printf '%s' "$component" | tr '/.' '__')"
        pid="$(cat "$tmpdir/$safe_name.pid")"
        if wait "$pid"; then
            status=0
        else
            status=$?
            overall_status=1
        fi
        printf '%s\n' "$status" >"$tmpdir/$safe_name.status"
    done

    for component in $components; do
        safe_name="$(printf '%s' "$component" | tr '/.' '__')"
        status="$(cat "$tmpdir/$safe_name.status")"

        if [ "$component" = ".." ]; then
            label="../"
        else
            label="$component"
        fi

        printf '===== %s =====\n' "$label"
        cat "$tmpdir/$safe_name.log"
        printf '\n[exit %s]\n\n' "$status"
    done

    rm -rf "$tmpdir"
    return "$overall_status"
}

if [ -z "$1" ]; then
    echo "Usage: $0 <component|all>" >&2
    exit 2
fi

if [ "$1" = "all" ]; then
    run_all_components_parallel
else
    run_component "$1"
fi
