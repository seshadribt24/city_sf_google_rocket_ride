import json
from datetime import datetime, timezone

import aiosqlite

from .seed_data import PILOT_INTERSECTIONS

import os

DB_PATH = os.environ.get("SAFECROSS_DB", "safecross.db")


async def get_db():
    return await aiosqlite.connect(DB_PATH)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tap_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intersection_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                event_time TEXT NOT NULL,
                crossing_id TEXT NOT NULL,
                card_type INTEGER NOT NULL,
                card_uid_hash TEXT NOT NULL,
                read_method INTEGER NOT NULL,
                filter_result TEXT NOT NULL,
                extension_sec INTEGER,
                phase_state_at_tap TEXT NOT NULL,
                snmp_result TEXT NOT NULL,
                risk_level TEXT DEFAULT 'unknown',
                vision_analysis TEXT,
                image_path TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                intersection_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                edge_status TEXT NOT NULL,
                reader_status TEXT NOT NULL,
                signal_controller_status TEXT NOT NULL,
                uptime_sec INTEGER NOT NULL,
                events_pending INTEGER NOT NULL,
                last_extension_time TEXT,
                software_version TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS intersections (
                intersection_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                crossings TEXT NOT NULL
            )
        """)
        # Migrate: add vision columns if missing
        cursor = await db.execute("PRAGMA table_info(tap_events)")
        existing_cols = {row[1] for row in await cursor.fetchall()}
        for col, typedef in [
            ("risk_level", "TEXT DEFAULT 'unknown'"),
            ("vision_analysis", "TEXT"),
            ("image_path", "TEXT"),
        ]:
            if col not in existing_cols:
                await db.execute(f"ALTER TABLE tap_events ADD COLUMN {col} {typedef}")

        # Seed intersections if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM intersections")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for i in PILOT_INTERSECTIONS:
                await db.execute(
                    "INSERT INTO intersections (intersection_id, device_id, name, lat, lng, crossings) VALUES (?, ?, ?, ?, ?, ?)",
                    (i["intersection_id"], i["device_id"], i["name"], i["lat"], i["lng"], json.dumps(i["crossings"])),
                )
        await db.commit()


async def insert_events(intersection_id: str, device_id: str, events: list[dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        for e in events:
            await db.execute(
                """INSERT INTO tap_events
                   (intersection_id, device_id, event_time, crossing_id, card_type,
                    card_uid_hash, read_method, filter_result, extension_sec,
                    phase_state_at_tap, snmp_result, risk_level, vision_analysis,
                    image_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    intersection_id, device_id,
                    str(e["event_time"]), e["crossing_id"], e["card_type"],
                    e["card_uid_hash"], e["read_method"], e["filter_result"],
                    e.get("extension_sec"), e["phase_state_at_tap"], e["snmp_result"],
                    e.get("risk_level", "unknown"),
                    json.dumps(e["vision_analysis"]) if e.get("vision_analysis") else None,
                    e.get("image_path"),
                ),
            )
        await db.commit()


async def insert_heartbeat(hb: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO heartbeats
               (device_id, intersection_id, timestamp, edge_status, reader_status,
                signal_controller_status, uptime_sec, events_pending,
                last_extension_time, software_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                hb["device_id"], hb["intersection_id"], str(hb["timestamp"]),
                hb["edge_status"], hb["reader_status"],
                hb["signal_controller_status"], hb["uptime_sec"],
                hb["events_pending"], str(hb["last_extension_time"]) if hb.get("last_extension_time") else None,
                hb["software_version"],
            ),
        )
        await db.commit()


async def get_events(since: datetime | None = None, intersection_id: str | None = None, limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tap_events WHERE 1=1"
        params = []
        if since:
            query += " AND event_time >= ?"
            params.append(str(since))
        if intersection_id:
            query += " AND intersection_id = ?"
            params.append(intersection_id)
        query += " ORDER BY event_time DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tap_events WHERE event_time >= ?", (today,)
        )
        total_taps = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tap_events WHERE event_time >= ? AND extension_sec IS NOT NULL AND extension_sec > 0",
            (today,),
        )
        total_extensions = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT AVG(extension_sec) FROM tap_events WHERE event_time >= ? AND extension_sec IS NOT NULL AND extension_sec > 0",
            (today,),
        )
        avg_ext = (await cursor.fetchone())[0] or 0

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT intersection_id) FROM tap_events WHERE event_time >= ?",
            (today,),
        )
        unique_intersections = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tap_events WHERE event_time >= ? AND snmp_result = 'success'",
            (today,),
        )
        accepted = (await cursor.fetchone())[0]
        acceptance_rate = (accepted / total_taps * 100) if total_taps > 0 else 0

        return {
            "total_taps_today": total_taps,
            "total_extensions_today": total_extensions,
            "avg_extension_sec": round(avg_ext, 1),
            "unique_intersections_active": unique_intersections,
            "acceptance_rate": round(acceptance_rate, 1),
        }


async def get_intersection_stats(intersection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get intersection info
        cursor = await db.execute(
            "SELECT * FROM intersections WHERE intersection_id = ?",
            (intersection_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        info = dict(row)
        info["crossings"] = json.loads(info["crossings"])

        # Today's tap count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM tap_events WHERE intersection_id = ? AND event_time >= ?",
            (intersection_id, today),
        )
        info["taps_today"] = (await cursor.fetchone())[0]

        # Hourly distribution (last 24h)
        info["hourly_distribution"] = await get_hourly_distribution(intersection_id)

        # Last 20 events
        cursor = await db.execute(
            "SELECT * FROM tap_events WHERE intersection_id = ? ORDER BY event_time DESC LIMIT 20",
            (intersection_id,),
        )
        rows = await cursor.fetchall()
        info["recent_events"] = [dict(r) for r in rows]

        # Latest heartbeat
        cursor = await db.execute(
            "SELECT * FROM heartbeats WHERE intersection_id = ? ORDER BY timestamp DESC LIMIT 1",
            (intersection_id,),
        )
        hb_row = await cursor.fetchone()
        info["latest_heartbeat"] = dict(hb_row) if hb_row else None

        return info


async def get_hourly_distribution(intersection_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = "SELECT event_time FROM tap_events WHERE event_time >= ?"
        params: list = [since]
        if intersection_id:
            query += " AND intersection_id = ?"
            params.append(intersection_id)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        hours = {h: 0 for h in range(24)}
        for row in rows:
            try:
                t = datetime.fromisoformat(row[0])
                hours[t.hour] += 1
            except (ValueError, IndexError):
                pass
        return [{"hour": h, "count": c} for h, c in sorted(hours.items())]


async def get_heatmap_data():
    async with aiosqlite.connect(DB_PATH) as db:
        since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await db.execute(
            """SELECT i.lat, i.lng, COUNT(e.id) as weight
               FROM tap_events e
               JOIN intersections i ON e.intersection_id = i.intersection_id
               WHERE e.event_time >= ?
               GROUP BY e.intersection_id""",
            (since,),
        )
        rows = await cursor.fetchall()
        return [{"lat": r[0], "lng": r[1], "weight": r[2]} for r in rows]


async def get_near_misses(since: datetime | None = None, limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT e.*, i.name as intersection_name
            FROM tap_events e
            LEFT JOIN intersections i ON e.intersection_id = i.intersection_id
            WHERE e.risk_level IN ('high', 'critical')
        """
        params: list = []
        if since:
            query += " AND e.event_time >= ?"
            params.append(str(since))
        query += " ORDER BY e.event_time DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("vision_analysis"):
                d["vision_analysis"] = json.loads(d["vision_analysis"])
            results.append(d)
        return results


async def get_risk_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                e.intersection_id,
                i.name,
                COUNT(*) as total_analyzed,
                SUM(CASE WHEN e.risk_level = 'high' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN e.risk_level = 'critical' THEN 1 ELSE 0 END) as critical_count
            FROM tap_events e
            LEFT JOIN intersections i ON e.intersection_id = i.intersection_id
            WHERE e.risk_level != 'unknown'
            GROUP BY e.intersection_id
            ORDER BY (SUM(CASE WHEN e.risk_level IN ('high','critical') THEN 1 ELSE 0 END)) DESC
        """)
        rows = await cursor.fetchall()
        return [
            {
                "intersection_id": r[0],
                "name": r[1],
                "total_analyzed": r[2],
                "high_count": r[3],
                "critical_count": r[4],
                "risk_rate": round((r[3] + r[4]) / r[2] * 100, 1) if r[2] > 0 else 0,
            }
            for r in rows
        ]
