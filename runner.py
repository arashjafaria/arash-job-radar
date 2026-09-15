import subprocess
import time
import datetime

CHECK_INTERVAL = 90

print("=" * 70)
print("ARASH JOB RADAR - CLOUD RUNNER")
print("=" * 70)

while True:

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("=" * 70)
    print("Starting BMW scan:", now)
    print("=" * 70)

    try:

        result = subprocess.run(
            ["python", "bmw_monitor.py"],
            check=False
        )

        print(
            "BMW scan finished with code:",
            result.returncode
        )

    except Exception as e:

        print("Runner error:")
        print(e)

    print()
    print(
        f"Waiting {CHECK_INTERVAL} seconds..."
    )

    time.sleep(CHECK_INTERVAL)