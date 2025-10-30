from fastapi import FastAPI
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, time
from typing import List, Optional, Literal
import pandas as pd

app = FastAPI(title="SmartDay Agent", version="0.1.0")

class TaskIn(BaseModel):
    name: str
    duration: float = Field(..., gt=0, description="hours")
    priority: Optional[Literal["low","medium","high"]] = "medium"
    constraint: Optional[str] = None  # "evening","morning","after:13:00","before:18:00"

class PlanRequest(BaseModel):
    available_hours: float
    start_time: Optional[str] = None  # "09:00"
    tasks: List[TaskIn]

class BlockOut(BaseModel):
    start: str
    end: str
    task: str
    notes: Optional[str] = None

class PlanResponse(BaseModel):
    date: str
    total_hours: float
    blocks: List[BlockOut]
    checklist: List[str]

def parse_clock(s: Optional[str], default: time) -> time:
    if not s:
        return default
    hh, mm = map(int, s.split(":"))
    return time(hh, mm)

def fits_constraint(t: time, constraint: Optional[str]) -> bool:
    if not constraint:
        return True
    c = constraint.lower()
    if c == "morning": return t < time(12,0)
    if c == "afternoon": return time(12,0) <= t < time(17,0)
    if c == "evening": return t >= time(16,30)
    if "after:" in c:
        hh, mm = map(int, c.split("after:")[1].split(":"))
        return t >= time(hh, mm)
    if "before:" in c:
        hh, mm = map(int, c.split("before:")[1].split(":"))
        return t < time(hh, mm)
    return True

def schedule(plan: PlanRequest) -> PlanResponse:
    today = datetime.now().date()
    start_clock = parse_clock(plan.start_time, default=time(9,0))
    cursor = datetime.combine(today, start_clock)
    end_limit = cursor + timedelta(hours=plan.available_hours)

    pri_rank = {"high":0, "medium":1, "low":2}
    tasks = sorted(
        plan.tasks,
        key=lambda t: (0 if t.constraint else 1, pri_rank.get(t.priority,1), -t.duration)
    )

    blocks = []
    checklist = []
    minutes_since_break = 0

    for task in tasks:
        dur = float(task.duration)
        probe = cursor
        step = timedelta(minutes=30)
        placed = False
        while probe + timedelta(hours=dur) <= end_limit:
            if fits_constraint(probe.time(), task.constraint):
                st = probe; en = probe + timedelta(hours=dur)
                blocks.append(BlockOut(
                    start=st.strftime("%H:%M"),
                    end=en.strftime("%H:%M"),
                    task=task.name.title(),
                    notes=(f"constraint={task.constraint}" if task.constraint else None)
                ))
                checklist.append(f"[ ] {task.name.title()} ({dur}h)")
                cursor = en
                minutes_since_break += int(dur*60)
                placed = True
                break
            probe += step
            if probe > cursor: cursor = probe

        if placed and minutes_since_break >= 150 and cursor + timedelta(minutes=15) <= end_limit:
            blocks.append(BlockOut(
                start=cursor.strftime("%H:%M"),
                end=(cursor+timedelta(minutes=15)).strftime("%H:%M"),
                task="Break",
                notes="recharge"
            ))
            cursor += timedelta(minutes=15)
            minutes_since_break = 0

    if cursor + timedelta(minutes=10) <= end_limit:
        blocks.append(BlockOut(
            start=cursor.strftime("%H:%M"),
            end=min(end_limit, cursor+timedelta(minutes=30)).strftime("%H:%M"),
            task="Wrap-up & Tomorrow Prep",
            notes="review & carry-over"
        ))

    df = pd.DataFrame([b.dict() for b in blocks])

    return PlanResponse(
        date=str(today),
        total_hours=plan.available_hours,
        blocks=[BlockOut(**row) for row in df.to_dict(orient="records")],
        checklist=checklist
    )

@app.post("/plan", response_model=PlanResponse)
def plan_endpoint(req: PlanRequest):
    return schedule(req)

@app.get("/health")
def health():
    return {"status":"ok","version":"0.1.0"}
