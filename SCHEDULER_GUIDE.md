# Telegram Bot Scheduler Guide

## Overview
This document explains how the scheduling system works in the Telegram bot. The bot uses APScheduler with a background scheduler to manage timed events like daily practices and test offers.

## Core Components

### 1. Scheduler Initialization
- Location: `bot.py` in `main()` function
- Type: `BackgroundScheduler`
- Timezone: UTC (all times in config are in UTC)
- Job store: Default in-memory store
- Executor: Thread pool executor

### 2. Key Configuration (config.py)

#### Time Configuration
All times are in UTC. Moscow Time (MSK) is UTC+3 (no DST).

```python
# === Daily Practice Times ===
MORNING_PRACTICE_TIME_UTC = datetime.time(hour=19, minute=45)  # 22:45 MSK
EVENING_PRACTICE_TIME_UTC = datetime.time(hour=19, minute=46)  # 22:46 MSK

# === Test Offer Times ===
# Day 3 test offer times
DAY3_KEY_TEST_OFFER_MORNING_UTC = datetime.time(7, 39)  # 10:39 MSK
DAY3_KEY_TEST_OFFER_EVENING_UTC = datetime.time(19, 39)  # 22:39 MSK
```

#### Special Days
- Day 3: Test offer day
- Day 14: Consultation offer day

### 3. Scheduler Jobs

#### Daily Practice Jobs
- **Trigger**: Daily at specified times
- **Function**: `send_daily_practice_job`
- **Parameters**:
  - `chat_id`: User's Telegram ID
  - `practice_type`: 'morning' or 'evening'
  - `day_number`: Current day in practice cycle (1-14)

#### Test Offer Jobs
- **Trigger**: On specific days (e.g., Day 3) at specified times
- **Function**: `offer_test_if_not_taken`
- **Parameters**:
  - `chat_id`: User's Telegram ID
  - `test_id`: ID of the test to offer
  - `is_day14`: Boolean for day 14 special handling
  - `test_for_day`: Day number for which the test is offered

### 4. User State Management

#### User Data Structure (users.json)
```json
{
  "<user_id>": {
    "subscribed_to_daily": boolean,
    "daily_practice_mode": "both"|"morning_only"|"none",
    "current_daily_day": number (1-14),
    "last_morning_sent_date": "ISO date string",
    "last_evening_sent_date": "ISO date string",
    "channel_subscription": boolean,
    "channel_subscription_checked": "ISO datetime string"
  }
}
```

### 5. Scheduling Logic

#### Practice Scheduling
1. When a user subscribes, `_schedule_daily_jobs_for_user` is called
2. For each practice type (morning/evening):
   - Remove any existing jobs for this user and practice type
   - Calculate next run time based on current time and scheduled time
   - Schedule the job using APScheduler

#### Timezone Handling
- All internal times are in UTC
- User-facing times are displayed in MSK (UTC+3)
- Conversion happens in the UI layer, not in scheduling logic

### 6. Common Issues and Solutions

#### Practices Not Sending
1. Check if the bot is running
2. Verify user's subscription status in users.json
3. Check logs for scheduler errors
4. Confirm system timezone is set to UTC

#### Time Mismatches
1. Ensure all times in config.py are in UTC
2. Verify the server's timezone is UTC
3. Check for DST-related issues (Moscow doesn't observe DST)

#### Job Duplication
1. The code should remove existing jobs before scheduling new ones
2. Check for multiple bot instances running

### 7. Testing the Scheduler

#### Manual Testing
1. Set practice times to 1-2 minutes in the future
2. Subscribe a test user
3. Monitor logs for job scheduling
4. Verify practice messages are sent

#### Automated Testing
1. Mock the scheduler in unit tests
2. Test time calculations
3. Verify job scheduling/removal logic

### 8. Maintenance

#### Logging
- All scheduler events are logged with level INFO or higher
- Look for "Scheduled" and "Removed job" messages

#### Monitoring
- Check bot's response to /status command
- Monitor error logs for scheduler exceptions

## Example Configuration

### For Testing
```python
# In config.py
MORNING_PRACTICE_TIME_UTC = datetime.time(
    hour=(datetime.datetime.utcnow() + datetime.timedelta(minutes=2)).hour,
    minute=(datetime.datetime.utcnow() + datetime.timedelta(minutes=2)).minute
)
EVENING_PRACTICE_TIME_UTC = datetime.time(
    hour=(datetime.datetime.utcnow() + datetime.timedelta(minutes=3)).hour,
    minute=(datetime.datetime.utcnow() + datetime.timedelta(minutes=3)).minute
)
```

### For Production
```python
# In config.py
# Morning practice at 10:00 MSK (07:00 UTC)
MORNING_PRACTICE_TIME_UTC = datetime.time(7, 0)

# Evening practice at 22:00 MSK (19:00 UTC)
EVENING_PRACTICE_TIME_UTC = datetime.time(19, 0)
```

## Troubleshooting

### Common Errors
1. "No trigger set" - Check job parameters
2. Timezone issues - Verify all times are in UTC
3. Missed jobs - Check system time and logs

### Log Analysis
Look for these log patterns:
- `Scheduling job...` - Job being scheduled
- `Removed job...` - Job being removed
- `Error in scheduler` - Scheduler errors

## Best Practices
1. Always use UTC for scheduling
2. Test time changes thoroughly
3. Monitor job execution
4. Keep the scheduler documentation updated
