#!/bin/sh
# Sauvegarde quotidienne (pg_dump compressé), 14 jours conservés.
set -eu
while true; do
  stamp=$(date -u +%Y%m%d-%H%M%S)
  pg_dump -h db -U primestone -Fc primestone > "/backups/primestone-$stamp.dump.tmp"
  mv "/backups/primestone-$stamp.dump.tmp" "/backups/primestone-$stamp.dump"
  find /backups -name 'primestone-*.dump' -mtime +14 -delete
  sleep 86400
done
