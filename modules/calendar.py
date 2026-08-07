import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import caldav
from caldav.lib.error import AuthorizationError
from icalendar import Calendar as ICalendar, Event as IEvent

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from credentials import read_json

CALDAV_URL = "https://caldav.icloud.com"
_icloud = read_json("icloud.json")
APPLE_ID = _icloud.get("ICLOUD_APPLE_ID")
APP_PASSWORD = _icloud.get("ICLOUD_APP_PASSWORD")
DEFAULT_CALENDAR = os.getenv("MONIKA_DEFAULT_CALENDAR", "")


def _local_tz():
    name = os.getenv("MONIKA_TIMEZONE")
    if name:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo


LOCAL_TZ = _local_tz()

CALENDAR_AGENT_INSTRUCTIONS = (
    "You are a calendar assistant, part of a larger home assistant chatbot. You manage the "
    "user's Apple iCloud calendar. For any request involving a relative date such as 'today', "
    "'tomorrow', 'this week', or 'Friday', call getCurrentDateTime FIRST so you can resolve it "
    "to an absolute date. Use listEvents to answer what is scheduled, and checkFreeBusy to "
    "answer whether the user is free at a given time. Use createEvent to add a new event; if "
    "the user does not name a calendar pass calendar_name as an empty string, and if they do "
    "not give a duration assume one hour. You can read the calendar and create new events, but "
    "you CANNOT edit or delete existing events -- if asked to do so, say so plainly. Every "
    "datetime you pass to a tool must be in the format YYYY-MM-DD HH:MM in the user's local "
    "time. Answer in brief, natural plaintext with no Markdown. Speak times conversationally, "
    "for example 'Friday at 3 PM', and do not read out raw timestamps."
)


# --- caldav helpers (blocking; run via asyncio.to_thread) ---------------------

_principal = None


def _get_principal():
    global _principal
    if _principal is None:
        client = caldav.DAVClient(
            url=CALDAV_URL, username=APPLE_ID, password=APP_PASSWORD, timeout=15
        )
        _principal = client.principal()
    return _principal


def _reset_principal():
    global _principal
    _principal = None


def _get_calendars():
    """Return iCloud calendars that hold events, excluding reminders/to-do lists."""
    calendars = []
    for c in _get_principal().calendars():
        try:
            components = c.get_supported_components()
        except Exception:
            components = []
        # keep event calendars; if the server is silent, keep it rather than drop a real one
        if not components or "VEVENT" in components:
            calendars.append(c)
    return calendars


def _resolve_calendar(calendars, requested_name):
    if not calendars:
        raise ValueError("No calendars were found on the iCloud account.")
    if requested_name:
        for c in calendars:
            if (c.name or "").lower() == requested_name.lower():
                return c
        raise ValueError(f"There is no calendar named '{requested_name}'.")
    if DEFAULT_CALENDAR:
        for c in calendars:
            if (c.name or "").lower() == DEFAULT_CALENDAR.lower():
                return c
    return calendars[0]


def _parse_local(value):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    raise ValueError(f"Could not parse the datetime '{value}'.")


def _to_local(value):
    """Normalize a date or datetime from an event into a tz-aware local datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(LOCAL_TZ)
    return datetime(value.year, value.month, value.day, tzinfo=LOCAL_TZ)


def _fmt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_local(value).strftime("%Y-%m-%d %H:%M")
    return value.strftime("%Y-%m-%d")


def _component_to_dict(cal_name, comp):
    dtstart = comp.get("dtstart")
    dtend = comp.get("dtend")
    start_val = dtstart.dt if dtstart is not None else None
    end_val = dtend.dt if dtend is not None else None
    return {
        "calendar": cal_name,
        "summary": str(comp.get("summary", "")),
        "start": _fmt(start_val),
        "end": _fmt(end_val),
        "all_day": start_val is not None and not isinstance(start_val, datetime),
        "location": str(comp.get("location", "")),
    }


def _search_events(start_dt, end_dt, calendar_name):
    calendars = _get_calendars()
    if calendar_name:
        calendars = [_resolve_calendar(calendars, calendar_name)]
    results = []
    for cal in calendars:
        cal_name = cal.name or ""
        for ev in cal.search(start=start_dt, end=end_dt, event=True, expand=True):
            for comp in ev.icalendar_instance.walk("VEVENT"):
                results.append((cal_name, comp))
    return results


def _overlaps(comp, win_start, win_end):
    dtstart = comp.get("dtstart")
    if dtstart is None:
        return False
    ev_start = _to_local(dtstart.dt)
    dtend = comp.get("dtend")
    ev_end = _to_local(dtend.dt) if dtend is not None else ev_start + timedelta(hours=1)
    return ev_start < win_end and ev_end > win_start


def _create_event(summary, start_dt, end_dt, all_day, location, description, calendar_name):
    cal = _resolve_calendar(_get_calendars(), calendar_name)
    ical = ICalendar()
    ical.add("prodid", "-//monika//calendar agent//EN")
    ical.add("version", "2.0")
    ev = IEvent()
    ev.add("uid", str(uuid.uuid4()))
    ev.add("summary", summary)
    ev.add("dtstamp", datetime.now(tz=LOCAL_TZ))
    if all_day:
        end_date = end_dt.date()
        if end_date <= start_dt.date():
            end_date = start_dt.date() + timedelta(days=1)
        ev.add("dtstart", start_dt.date())
        ev.add("dtend", end_date)
    else:
        ev.add("dtstart", start_dt)
        ev.add("dtend", end_dt)
    if location:
        ev.add("location", location)
    if description:
        ev.add("description", description)
    ical.add_component(ev)
    cal.save_event(ical.to_ical())
    return cal.name or ""


# --- tool result helpers ------------------------------------------------------

def _ok(text):
    return {"content": [{"type": "text", "text": text}]}


def _error(text):
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _creds_missing():
    if not APPLE_ID or not APP_PASSWORD:
        return _error("ICLOUD_APPLE_ID or ICLOUD_APP_PASSWORD is not configured in ~/.credentials/icloud.json.")
    return None


def _translate(exc):
    """Turn a caldav/network exception into a tool error result."""
    if isinstance(exc, AuthorizationError):
        reason = (getattr(exc, "reason", "") or "").lower()
        if "forbidden" in reason:
            return _error(
                "iCloud refused that operation (403 Forbidden). The target calendar may be "
                "read-only or a reminders list rather than an events calendar."
            )
        _reset_principal()
        return _error(
            "iCloud authentication failed. Check ICLOUD_APPLE_ID and that ICLOUD_APP_PASSWORD "
            "is a valid app-specific password generated at appleid.apple.com."
        )
    return _error(f"Could not reach the iCloud calendar: {exc}")


# --- MCP tools ----------------------------------------------------------------

@tool(
    "getCurrentDateTime",
    "Gets the current local date, time, weekday, and timezone. Call this FIRST for any "
    "request involving a relative date such as 'tomorrow', 'this week', or 'Friday'.",
    {},
)
async def get_current_datetime(args):
    now = datetime.now(tz=LOCAL_TZ)
    tzname = getattr(LOCAL_TZ, "key", None) or now.strftime("%Z")
    return _ok(f"{now.strftime('%Y-%m-%d %H:%M')} ({now.strftime('%A')}, {tzname})")


@tool(
    "listCalendars",
    "Lists the calendars available on the user's iCloud account. Also confirms the iCloud "
    "connection is working. Returns a JSON object with the calendar names and the default one "
    "used when creating events.",
    {},
)
async def list_calendars(args):
    missing = _creds_missing()
    if missing:
        return missing
    try:
        cals = await asyncio.to_thread(_get_calendars)
    except Exception as e:
        return _translate(e)
    names = [c.name or "(unnamed)" for c in cals]
    if not names:
        return _error("No calendars were found on the iCloud account.")
    default = await asyncio.to_thread(lambda: (_resolve_calendar(cals, "").name or "(unnamed)"))
    return _ok(json.dumps({"calendars": names, "default": default}))


@tool(
    "listEvents",
    "Lists calendar events between two datetimes. start and end must be 'YYYY-MM-DD HH:MM' in "
    "the user's local time. Recurring events are expanded into individual occurrences. Pass "
    "calendar_name to limit to one calendar, or '' to search every calendar.",
    {"start": str, "end": str, "calendar_name": str},
)
async def list_events(args):
    missing = _creds_missing()
    if missing:
        return missing
    try:
        start_dt = _parse_local(args["start"])
        end_dt = _parse_local(args["end"])
    except (ValueError, KeyError):
        return _ok("The start and end must be 'YYYY-MM-DD HH:MM'. Call getCurrentDateTime and try again.")
    try:
        pairs = await asyncio.to_thread(
            _search_events, start_dt, end_dt, args.get("calendar_name", "")
        )
    except ValueError as e:
        return _ok(str(e))
    except Exception as e:
        return _translate(e)
    events = [_component_to_dict(name, comp) for name, comp in pairs]
    events.sort(key=lambda e: e["start"] or "")
    return _ok(json.dumps({"events": events}))


@tool(
    "checkFreeBusy",
    "Checks whether the user is free during a time window. start and end must be "
    "'YYYY-MM-DD HH:MM' in local time. Returns 'free', or the list of conflicting events.",
    {"start": str, "end": str},
)
async def check_free_busy(args):
    missing = _creds_missing()
    if missing:
        return missing
    try:
        start_dt = _parse_local(args["start"])
        end_dt = _parse_local(args["end"])
    except (ValueError, KeyError):
        return _ok("The start and end must be 'YYYY-MM-DD HH:MM'. Call getCurrentDateTime and try again.")
    try:
        pairs = await asyncio.to_thread(_search_events, start_dt, end_dt, "")
    except Exception as e:
        return _translate(e)
    conflicts = [
        _component_to_dict(name, comp)
        for name, comp in pairs
        if _overlaps(comp, start_dt, end_dt)
    ]
    if conflicts:
        return _ok(json.dumps({"status": "busy", "conflicts": conflicts}))
    return _ok(json.dumps({"status": "free"}))


@tool(
    "createEvent",
    "Creates a new calendar event. start and end are 'YYYY-MM-DD HH:MM' in the user's local "
    "time. Set all_day true for a date-only event (the time portion is then ignored). Pass "
    "location and description as '' when not given, and calendar_name as '' to use the default "
    "calendar. This tool can only add events; it cannot edit or delete them.",
    {
        "summary": str,
        "start": str,
        "end": str,
        "all_day": bool,
        "location": str,
        "description": str,
        "calendar_name": str,
    },
)
async def create_event(args):
    missing = _creds_missing()
    if missing:
        return missing
    summary = (args.get("summary") or "").strip()
    if not summary:
        return _ok("An event needs a title. Please tell me what the event is.")
    all_day = bool(args.get("all_day"))
    try:
        start_dt = _parse_local(args["start"])
        end_dt = _parse_local(args["end"])
    except (ValueError, KeyError):
        return _ok("The start and end must be 'YYYY-MM-DD HH:MM'. Call getCurrentDateTime and try again.")
    if not all_day and end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)
    try:
        cal_name = await asyncio.to_thread(
            _create_event,
            summary,
            start_dt,
            end_dt,
            all_day,
            args.get("location", ""),
            args.get("description", ""),
            args.get("calendar_name", ""),
        )
    except ValueError as e:
        return _ok(str(e))
    except Exception as e:
        return _translate(e)
    when = start_dt.strftime("%Y-%m-%d") if all_day else start_dt.strftime("%Y-%m-%d %H:%M")
    return _ok(json.dumps({"status": "created", "summary": summary, "start": when, "calendar": cal_name}))


calendar_tools_server = create_sdk_mcp_server(
    name="calendar_tools",
    version="1.0.0",
    tools=[get_current_datetime, list_calendars, list_events, check_free_busy, create_event],
)


def build_calendar_agent(model: str):
    @tool(
        "calendar_agent",
        "Routes calendar questions and event creation to a specialized Apple Calendar agent. "
        "Pass the user's request as 'request'.",
        {"request": str},
    )
    async def calendar_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=CALENDAR_AGENT_INSTRUCTIONS,
                mcp_servers={"calendar_tools": calendar_tools_server},
                allowed_tools=[
                    "mcp__calendar_tools__getCurrentDateTime",
                    "mcp__calendar_tools__listCalendars",
                    "mcp__calendar_tools__listEvents",
                    "mcp__calendar_tools__checkFreeBusy",
                    "mcp__calendar_tools__createEvent",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return calendar_agent
