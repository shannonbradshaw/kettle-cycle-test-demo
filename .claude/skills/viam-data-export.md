---
name: viam-data-export
description: Patterns for exporting and analyzing Viam sensor data via CLI
---

# Viam Data Export and Analysis

## Exporting Tabular Sensor Data

```bash
viam data export tabular \
  --destination=/tmp/sensor-data \
  --part-id=<part_id> \
  --resource-name=<sensor_name> \
  --resource-subtype=rdk:component:sensor \
  --method=Readings
```

**Key flags:**
- `--resource-subtype` must be full API path: `rdk:component:sensor` (not just `sensor`)
- `--method` is typically `Readings` for sensors
- `--start` and `--end` accept ISO-8601 timestamps for time filtering

**Get IDs from machine.json:**
```bash
cat machine.json | jq '{part_id, machine_id, org_id}'
```

## Data Format

Output is NDJSON (newline-delimited JSON). Each line:
```json
{
  "partId": "...",
  "resourceName": "force-sensor",
  "resourceSubtype": "rdk:component:sensor",
  "methodName": "Readings",
  "timeCaptured": "2026-01-20T13:06:36.907Z",
  "payload": {
    "readings": {
      "capture_state": "capturing",
      "cycle_count": 3,
      "max_force": 200,
      "sample_count": 100,
      "samples": [71, 74, 77, ...],
      "should_sync": true,
      "trial_id": "trial-20260120-080817"
    }
  }
}
```

## Analysis Patterns

**Find unique values:**
```bash
grep -o '"trial_id":"[^"]*"' data.ndjson | sort -u
grep -o '"cycle_count":[0-9]*' data.ndjson | sort -u
```

**Count by field value:**
```bash
grep -c '"should_sync":true' data.ndjson
grep -c '"should_sync":false' data.ndjson
```

**Filter with jq (for smaller datasets or sampled data):**
```bash
# Readings with samples
cat data.ndjson | jq -c 'select(.payload.readings.sample_count > 0)'

# Readings from specific trial
grep '"trial_id":"trial-123"' data.ndjson | jq -s '{
  total: length,
  max_force: ([.[].payload.readings.max_force // 0] | max),
  max_samples: ([.[].payload.readings.sample_count] | max)
}'

# Extract sample array from full capture
grep '"sample_count":100' data.ndjson | head -1 | jq '.payload.readings.samples'
```

**For large files (800MB+):**
- Use `grep` for filtering before `jq` (much faster)
- Use `head -N` or `tail -N` to sample data
- Avoid complex jq on full file (memory issues)

## Conditional Sync Analysis

The `should_sync` field determines if data uploads to cloud:
- `true` during active trials (trial_id is set)
- `false` during idle time

To see only trial data:
```bash
grep '"should_sync":true' data.ndjson | wc -l
```

## Common Issues

1. **Empty results**: Check `--resource-subtype` uses full path `rdk:component:sensor`
2. **Permission denied in jq**: Large file + complex query; use grep to filter first
3. **Memory issues**: Don't load entire file into jq; stream or sample instead
