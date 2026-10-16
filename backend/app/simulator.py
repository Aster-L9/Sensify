"""
Telemetry simulator — generates live telemetry data for active runs.
Runs as a background task, writes to DB on interval.
"""
import math
import random
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Run, Segment, Telemetry, RunStatus


class TelemetrySimulator:
    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self.running = False
        self._task = None
        self._counters: dict[int, int] = {}  # run_id -> tick counter

    async def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        print(f"Telemetry simulator started (interval={self.interval}s)")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("Telemetry simulator stopped")

    async def _loop(self):
        while self.running:
            try:
                self._generate_tick()
            except Exception as e:
                print(f"Simulator error: {e}")
            await asyncio.sleep(self.interval)

    def _generate_tick(self):
        db: Session = SessionLocal()
        try:
            active_runs = db.query(Run).filter(Run.status == RunStatus.active.value).all()
            segments = db.query(Segment).all()

            for run in active_runs:
                counter = self._counters.get(run.id, 0)
                self._counters[run.id] = counter + 1
                rng = random.Random(run.seed + counter)

                for seg in segments:
                    now = datetime.utcnow()
                    base_pressure = 950 + (seg.id * 37 % 200)
                    base_flow = 800 + (seg.id * 53 % 600)
                    base_temp = 75 + (seg.id * 17 % 30)

                    hour_factor = math.sin(counter * math.pi / 24) * 15
                    pressure = base_pressure + hour_factor + rng.gauss(0, 8)
                    flow = base_flow + hour_factor * 2 + rng.gauss(0, 15)
                    temp = base_temp + math.sin(counter * math.pi / 48) * 5 + rng.gauss(0, 1.5)

                    # Ground truth
                    db.add(Telemetry(
                        run_id=run.id, segment_id=seg.id, timestamp=now,
                        pressure_psi=round(pressure, 2),
                        flow_rate_bph=round(flow, 2),
                        temperature_f=round(temp, 2),
                        is_ground_truth=True,
                    ))
                    # Reported
                    db.add(Telemetry(
                        run_id=run.id, segment_id=seg.id, timestamp=now,
                        pressure_psi=round(pressure + rng.gauss(0, 3), 2),
                        flow_rate_bph=round(flow + rng.gauss(0, 8), 2),
                        temperature_f=round(temp + rng.gauss(0, 0.5), 2),
                        is_ground_truth=False,
                    ))

                db.commit()
        finally:
            db.close()


# Singleton instance
simulator = TelemetrySimulator(interval_seconds=30)
