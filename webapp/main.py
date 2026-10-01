"""
webapp/main.py

A small, standalone web dashboard showing user growth for the CONQUEER bot.
Reads from the SAME Postgres database the bot uses — no new database needed.

Deployed as a SEPARATE Railway service pointing at this same repo,
with a custom start command (see deployment notes at the bottom of this file).
"""

import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select

from database.connect import async_session
from database.models.user import UserModel

app = FastAPI(title="CONQUEER Dashboard")
security = HTTPBasic()

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")  # MUST be set in Railway variables


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not DASHBOARD_PASSWORD:
        raise HTTPException(status_code=500, detail="DASHBOARD_PASSWORD not configured")

    correct_user = secrets.compare_digest(credentials.username, DASHBOARD_USER)
    correct_pass = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)

    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.get("/api/stats")
async def get_stats(authorized: bool = Depends(check_auth)):
    """Returns total users, joins today/this week, and daily joins for the last 30 days."""
    async with async_session() as session:
        total_result = await session.execute(select(func.count(UserModel.id)))
        total_users = total_result.scalar() or 0

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        today_result = await session.execute(
            select(func.count(UserModel.id)).where(UserModel.created_at >= today_start)
        )
        joins_today = today_result.scalar() or 0

        week_result = await session.execute(
            select(func.count(UserModel.id)).where(UserModel.created_at >= week_start)
        )
        joins_this_week = week_result.scalar() or 0

        thirty_days_ago = today_start - timedelta(days=30)
        daily_result = await session.execute(
            select(
                func.date_trunc("day", UserModel.created_at).label("day"),
                func.count(UserModel.id).label("count"),
            )
            .where(UserModel.created_at >= thirty_days_ago)
            .group_by("day")
            .order_by("day")
        )
        daily_rows = daily_result.all()

        # Fill in missing days with 0 so the chart has no gaps
        daily_map = {row.day.date().isoformat(): row.count for row in daily_rows}
        daily_series = []
        for i in range(30, -1, -1):
            day = (today_start - timedelta(days=i)).date().isoformat()
            daily_series.append({"date": day, "count": daily_map.get(day, 0)})

        recent_result = await session.execute(
            select(UserModel.id, UserModel.username, UserModel.created_at)
            .order_by(UserModel.created_at.desc())
            .limit(20)
        )
        recent_users = [
            {
                "id": row.id,
                "username": row.username or "—",
                "joined": row.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            }
            for row in recent_result.all()
        ]

    return JSONResponse({
        "total_users": total_users,
        "joins_today": joins_today,
        "joins_this_week": joins_this_week,
        "daily_series": daily_series,
        "recent_users": recent_users,
    })


@app.get("/", response_class=HTMLResponse)
async def dashboard(authorized: bool = Depends(check_auth)):
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CONQUEER Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff; margin: 0; padding: 24px; }
        h1 { margin-bottom: 4px; }
        .subtitle { color: #888; margin-bottom: 24px; }
        .cards { display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }
        .card { background: #1a1a1a; border-radius: 12px; padding: 20px 28px; flex: 1; min-width: 160px; border: 1px solid #2a2a2a; }
        .card .label { color: #888; font-size: 0.85rem; margin-bottom: 6px; }
        .card .value { font-size: 2rem; font-weight: 700; }
        .chart-container { background: #1a1a1a; border-radius: 12px; padding: 24px; margin-bottom: 32px; border: 1px solid #2a2a2a; }
        table { width: 100%; border-collapse: collapse; background: #1a1a1a; border-radius: 12px; overflow: hidden; }
        th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid #2a2a2a; font-size: 0.9rem; }
        th { color: #888; font-weight: 600; }
        #loading { color: #888; }
    </style>
</head>
<body>
    <h1>👑 CONQUEER Dashboard</h1>
    <div class="subtitle">Live user growth</div>
    <div id="loading">Loading...</div>
    <div id="content" style="display:none;">
        <div class="cards">
            <div class="card"><div class="label">Total Users</div><div class="value" id="total">—</div></div>
            <div class="card"><div class="label">Joined Today</div><div class="value" id="today">—</div></div>
            <div class="card"><div class="label">Joined This Week</div><div class="value" id="week">—</div></div>
        </div>
        <div class="chart-container">
            <canvas id="chart" height="80"></canvas>
        </div>
        <h3>Recent Joins</h3>
        <table>
            <thead><tr><th>Username</th><th>User ID</th><th>Joined</th></tr></thead>
            <tbody id="recent-table"></tbody>
        </table>
    </div>

    <script>
        fetch('/api/stats', { credentials: 'include' })
            .then(r => r.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';

                document.getElementById('total').textContent = data.total_users;
                document.getElementById('today').textContent = data.joins_today;
                document.getElementById('week').textContent = data.joins_this_week;

                const ctx = document.getElementById('chart').getContext('2d');
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.daily_series.map(d => d.date.slice(5)),
                        datasets: [{
                            label: 'New users per day',
                            data: data.daily_series.map(d => d.count),
                            borderColor: '#f43f5e',
                            backgroundColor: 'rgba(244, 63, 94, 0.1)',
                            fill: true,
                            tension: 0.3,
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { labels: { color: '#fff' } } },
                        scales: {
                            x: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' } },
                            y: { ticks: { color: '#888' }, grid: { color: '#2a2a2a' }, beginAtZero: true }
                        }
                    }
                });

                const tbody = document.getElementById('recent-table');
                data.recent_users.forEach(u => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>@${u.username}</td><td>${u.id}</td><td>${u.joined}</td>`;
                    tbody.appendChild(tr);
                });
            });
    </script>
</body>
</html>
"""