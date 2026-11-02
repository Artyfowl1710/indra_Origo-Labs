#!/bin/bash

# Daily Backup Script
# Creates dated backups of files in a source directory, compresses with gzip
# and stores them in a dated folder structure.

set -euo pipefail

# Usage: ./backup_daily.sh --source /path/to/source --retention 7 --log /path/to/log.txt
# Arguments:
#   --source       Source directory to backup (required)
#   --retention    Number of days to keep backups (default: 7)
#   --log          Path to log file (default: /tmp/backup.log)
#   --help         Show this help message

usage() {
    cat <<EOF
Usage: $0 --source <dir> --retention <days> [--log <logfile>]

Creates a daily backup of all files in <dir>, compresses with gzip,
and stores in dated folder structure.

Arguments:
  --source       Source directory to backup (required)
  --retention    Number of days to keep backups (default: 7)
  --log          Path to log file (default: /tmp/backup.log)
  --help         Show this help message

Examples:
  $0 --source /data --retention 30 --log /var/log/backup.log
  $0 --source /home/user/data --retention 7
EOF
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --source)
            SOURCE_DIR="$2"
            shift 2
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --log)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SOURCE_DIR" ]]; then
    echo "Error: --source argument is required" >&2
    usage
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: Source directory does not exist: $SOURCE_DIR" >&2
    exit 1
fi

# Set defaults
RETENTION_DAYS=${RETENTION_DAYS:-7}
LOG_FILE=${LOG_FILE:-/tmp/backup.log}

# Ensure log directory exists
LOG_DIR=$(dirname "$LOG_FILE")
if [[ ! -d "$LOG_DIR" ]]; then
    mkdir -p "$LOG_DIR" 2>/dev/null || echo "Warning: Could not create log directory: $LOG_DIR" >&2
fi

# Create log
LOG_MSG() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

LOG_MSG "=== Daily Backup Started ==="
LOG_MSG "Source: $SOURCE_DIR"
LOG_MSG "Retention: $RETENTION_DAYS days"
LOG_MSG "Log: $LOG_FILE"

# Create backup date and destination directory
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${SOURCE_DIR}/backup_${BACKUP_DATE}"

# Validate source directory
if [[ ! -d "$SOURCE_DIR" ]]; then
    LOG_MSG "ERROR: Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Check if directory is not empty
if [[ -z "$(ls -A "$SOURCE_DIR" 2>/dev/null)" ]]; then
    LOG_MSG "Warning: Source directory is empty"
    exit 0
fi

# Create backup directory
mkdir -p "$BACKUP_DIR" || {
    LOG_MSG "ERROR: Cannot create backup directory: $BACKUP_DIR"
    exit 1
}

# Create backup archive (tar + gzip)
ARCHIVE_NAME="backup_${BACKUP_DATE}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"
LOG_MSG "Creating backup archive: $ARCHIVE_PATH"

# Compress source directory to tar.gz
tar -czf "$ARCHIVE_PATH" -C "$SOURCE_DIR" . 2>&1 | tee -a "$LOG_FILE"

if [[ $? -eq 0 ]]; then
    LOG_MSG "Backup created successfully: $ARCHIVE_PATH"
    LOG_MSG "Archive size: $(du -h "$ARCHIVE_PATH" | cut -f1)"
else
    LOG_MSG "ERROR: Backup creation failed"
    exit 1
fi

# Clean up old backups
LOG_MSG "Cleaning up backups older than $RETENTION_DAYS days..."

# Find and remove old backup directories
OLD_BACKUPS=$(find "$SOURCE_DIR" -maxdepth 1 -name "backup_*" -type d -mtime +$RETENTION_DAYS 2>/dev/null || true)

if [[ -n "$OLD_BACKUPS" ]]; then
    REMOVED_COUNT=0
    for old_backup in $OLD_BACKUPS; do
        LOG_MSG "Removing old backup: $old_backup"
        rm -rf "$old_backup"
        ((REMOVED_COUNT++)) || true
    done
    LOG_MSG "Removed $REMOVED_COUNT old backup(s)"
else
    LOG_MSG "No old backups found to remove"
fi

# Cleanup temporary files in source directory (optional)
TEMP_FILES=$(find "$SOURCE_DIR" -name "*.tmp" -type f 2>/dev/null || true)
if [[ -n "$TEMP_FILES" ]]; then
    find "$SOURCE_DIR" -name "*.tmp" -type f -delete 2>/dev/null || true
    LOG_MSG "Cleaned up temporary files"
fi

# Verify archive integrity
LOG_MSG "Verifying archive integrity..."
if tar -tzf "$ARCHIVE_PATH" > /dev/null 2>&1; then
    LOG_MSG "Archive integrity verified successfully"
else
    LOG_MSG "ERROR: Archive integrity check failed"
    exit 1
fi

LOG_MSG "=== Daily Backup Completed Successfully ==="
LOG_MSG "Backup: $ARCHIVE_PATH"
LOG_MSG "Source size: $(du -sh "$SOURCE_DIR" | cut -f1)"
