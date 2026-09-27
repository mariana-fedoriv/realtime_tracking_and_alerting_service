"""Async load generator that simulates many devices reporting GPS coordinates.

A fixed pool of N worker coroutines (--concurrency, default 500) is created.
Each worker owns a slice of the device list and cycles through it continuously:
drift → POST → move to next device, sleeping one interval per full cycle.

This keeps the asyncio task count at N (e.g. 500) rather than D (e.g. 10,000),
eliminating the event-loop overhead that caused each device to miss most of its
intended firing windows when running one-task-per-device. The connection pool
is sized to N so every worker can have a live keep-alive connection at all times.

On a 503 (ingestion queue full) the sending worker backs off briefly before
retrying, mirroring how a real client should react to server backpressure.

Usage:
    python generator.py --devices 10000 --base-url http://localhost:8000 --interval 3
"""

import argparse
import asyncio
import math
import random
import time

import httpx

EARTH_RADIUS_M = 6_371_000


class SimulatedDevice:
    def __init__(self, device_id: str, latitude: float, longitude: float) -> None:
        self.device_id = device_id
        self.latitude = latitude
        self.longitude = longitude

    def drift(self, max_delta_m: float) -> None:
        """Nudge the position by a small random delta (roughly max_delta_m)."""
        delta_lat_m = random.uniform(-max_delta_m, max_delta_m)
        delta_lon_m = random.uniform(-max_delta_m, max_delta_m)
        self.latitude += (delta_lat_m / EARTH_RADIUS_M) * (180 / math.pi)
        self.longitude += (
            (delta_lon_m / EARTH_RADIUS_M)
            * (180 / math.pi)
            / max(0.1, abs(math.cos(math.radians(self.latitude))))
        )
        self.latitude = max(-90.0, min(90.0, self.latitude))
        self.longitude = max(-180.0, min(180.0, ((self.longitude + 180) % 360) - 180))


async def _post(
    client: httpx.AsyncClient,
    base_url: str,
    device: SimulatedDevice,
    stats: dict,
) -> None:
    payload = {
        "device_id": device.device_id,
        "latitude": device.latitude,
        "longitude": device.longitude,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    backoff = 0.5
    for _ in range(5):
        try:
            response = await client.post(f"{base_url}/api/v1/devices/location", json=payload)
        except httpx.HTTPError:
            stats["errors"] += 1
            return
        if response.status_code == 202:
            stats["sent"] += 1
            return
        if response.status_code == 503:
            stats["backpressure"] += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5.0)
            continue
        stats["errors"] += 1
        return


async def batch_worker(
    worker_id: int,
    devices: list[SimulatedDevice],
    client: httpx.AsyncClient,
    base_url: str,
    interval: float,
    drift_m: float,
    stop_at: float,
    stats: dict,
) -> None:
    """Cycle through a slice of devices continuously.

    One sleep of `interval` per full cycle keeps per-device cadence at the
    right frequency without spawning a separate asyncio task per device.
    Workers are staggered by a small random jitter (up to 200 ms) only at
    startup to avoid a simultaneous TCP-connect storm; after that all workers
    run concurrently so the full connection pool stays utilised.
    """
    await asyncio.sleep(random.uniform(0, 0.2))

    while time.monotonic() < stop_at:
        cycle_start = time.monotonic()

        for device in devices:
            if time.monotonic() >= stop_at:
                return
            device.drift(drift_m)
            await _post(client, base_url, device, stats)

        # Sleep for whatever remains of the interval after the cycle completed.
        # If the cycle took longer than the interval (overloaded), skip the sleep
        # so we don't fall further behind.
        elapsed = time.monotonic() - cycle_start
        remaining = interval - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=10_000)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--interval", type=float, default=3.0, help="seconds between reports per device")
    parser.add_argument("--drift-m", type=float, default=15.0, help="max meters of drift per tick")
    parser.add_argument("--duration", type=float, default=120.0, help="seconds to run the simulation")
    parser.add_argument(
        "--concurrency", type=int, default=500,
        help="number of worker coroutines (= max concurrent HTTP connections)"
    )
    args = parser.parse_args()

    devices = [
        SimulatedDevice(
            device_id=f"device-{i:06d}",
            latitude=random.uniform(-60, 60),
            longitude=random.uniform(-180, 180),
        )
        for i in range(args.devices)
    ]

    # Split devices evenly across workers. Last worker may get fewer devices
    # if args.devices isn't divisible by args.concurrency.
    n_workers = min(args.concurrency, args.devices)
    slices = [devices[i::n_workers] for i in range(n_workers)]

    stats: dict = {"sent": 0, "errors": 0, "backpressure": 0, "_n_workers": n_workers}
    stop_at = time.monotonic() + args.duration

    limits = httpx.Limits(max_connections=n_workers, max_keepalive_connections=n_workers)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        reporter = asyncio.create_task(_report_progress(stats, stop_at))
        await asyncio.gather(
            *(
                batch_worker(i, slices[i], client, args.base_url, args.interval, args.drift_m, stop_at, stats)
                for i in range(n_workers)
            )
        )
        reporter.cancel()

    print(
        f"Done. sent={stats['sent']} errors={stats['errors']} "
        f"backpressure_retries={stats['backpressure']}"
    )


async def _report_progress(stats: dict, stop_at: float) -> None:
    while time.monotonic() < stop_at:
        await asyncio.sleep(5)
        print(
            f"[{time.strftime('%H:%M:%S')}] sent={stats['sent']} "
            f"errors={stats['errors']} backpressure_retries={stats['backpressure']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
