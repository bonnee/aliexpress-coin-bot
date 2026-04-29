#!/bin/sh

set -e

# Default values
TZ=${TZ:-"UTC"}
CRON_SCHEDULE=${CRON_SCHEDULE:-"0 0 * * *"}
RUN_ON_STARTUP=${RUN_ON_STARTUP:-"true"}
RUN_ONCE=${RUN_ONCE:-"false"}

# Set timezone
if [ -e /usr/share/zoneinfo/"$TZ" ]; then
    echo "Setting timezone: $TZ"
    ln -snf /usr/share/zoneinfo/"$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
fi

# If RUN_ON_STARTUP is set, run it once before setting up the schedule
if [ "$RUN_ON_STARTUP" = "true" ]; then
    echo "Running collector on startup..."
    python collect_coins.py
fi

# If RUN_ONCE is set to true, exit after the first run
if [ "$RUN_ONCE" = "true" ]; then
    echo "RUN_ONCE is true, exiting..."
    exit 0
fi

# Schedule the process using cron
echo "Setting up cron schedule: $CRON_SCHEDULE"
# Save environment variables for cron
printenv | grep -v "no_proxy" > /app/project_env.sh
sed -i 's/^\(.*\)$/export \1/g' /app/project_env.sh

# Create the crontab
echo "$CRON_SCHEDULE . /app/project_env.sh && cd /app && python /app/collect_coins.py >> /app/collection_log.txt 2>&1" | crontab -

# Run cron in the foreground
echo "Starting cron..."
cron -f
