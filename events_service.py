import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

import requests
from geopy.geocoders import Nominatim
import geopy.distance
from concurrent.futures import ThreadPoolExecutor, as_completed


# Backend defaults for API keys (used if none are provided)
DEFAULT_TM_API_KEY = "VHANTNxOcGFfpUD3k3whDbU1TiqBfbGs"
DEFAULT_EB_API_KEY = "272DADRV35ZXG3IS55"

@dataclass
class Event:
    title: str
    date: datetime
    location: str
    latitude: float
    longitude: float
    url: str
    source: str
    image_url: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    currency: str = ""


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _to_local_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def geocode_zip(zip_code: str) -> Optional[Tuple[float, float]]:
    try:
        geocoder = Nominatim(user_agent="events_app_zip")
        loc = geocoder.geocode({"postalcode": zip_code, "country": "USA"}, timeout=10)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception:
        pass
    return None


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return geopy.distance.geodesic((lat1, lon1), (lat2, lon2)).miles


# Removed legacy HTML scraping helpers (Meetup/Eventbrite) to focus solely on Ticketmaster for performance


# Meetup/Eventbrite support removed


# Eventbrite support removed


def _to_tm_iso(dt: datetime) -> str:
    """Ticketmaster expects ISO8601 UTC with 'Z'."""
    if dt.tzinfo is None:
        dt = dt.astimezone()  # make aware in local timezone
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _to_eb_iso(dt: datetime) -> str:
    """Eventbrite expects ISO8601 UTC with 'Z'."""
    return _to_tm_iso(dt)


def fetch_ticketmaster_events(lat: float, lon: float, radius_miles: float, start_date: datetime, end_date: datetime, api_key: Optional[str]) -> List[Event]:
    # Use provided key or fallback to backend default
    api_key = api_key or DEFAULT_TM_API_KEY
    try:
        url = "https://app.ticketmaster.com/discovery/v2/events.json"
        out: List[Event] = []
        page = 0
        total_pages = 1
        def _tm_event_url(ev: Dict) -> str:
            """Return a stable, user-facing Ticketmaster event URL.

            Prefer the API's `url` field; if missing or suspicious, build
            a canonical URL from the event `id`.
            """
            raw = (ev.get("url") or "").strip()
            if raw and raw.startswith("http"):
                return raw
            # Fallback: construct from event id
            ev_id = (ev.get("id") or "").strip()
            if ev_id:
                return f"https://www.ticketmaster.com/event/{ev_id}"
            return ""
        # First request to get totalPages
        params_base = {
            "apikey": api_key,
            "latlong": f"{lat},{lon}",
            "radius": round(radius_miles*1.60934),
            "unit": "km",
            "size": 200,
            "startDateTime": _to_tm_iso(start_date),
            "endDateTime": _to_tm_iso(end_date + timedelta(days=1)),
            "sort": "date,asc",
        }
        resp0 = requests.get(url, params={**params_base, "page": 0}, timeout=12)
        if resp0.status_code in (401, 403):
            raise ValueError("Ticketmaster API key is invalid or unauthorized.")
        if resp0.status_code != 200:
            return []
        data0 = resp0.json()
        items0 = data0.get("_embedded", {}).get("events", [])
        pg0 = data0.get("page", {})
        total_pages = int(pg0.get("totalPages", 1)) or 1
        # Process first page
        for ev in items0:
                name = ev.get("name") or "Ticketmaster Event"
                ds = ev.get("dates", {}).get("start", {})
                dt_text = ds.get("dateTime") or ds.get("localDate")
                if not dt_text:
                    continue
                try:
                    dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
                except Exception:
                    try:
                        dt = datetime.strptime(dt_text[:10], "%Y-%m-%d")
                    except Exception:
                        continue
                dt = _to_local_naive(dt)
                venue = (ev.get("_embedded", {}).get("venues", [{}])[0])
                vlat = float(venue.get("location", {}).get("latitude", lat))
                vlon = float(venue.get("location", {}).get("longitude", lon))
                loc = venue.get("name") or ""
                tm_url = _tm_event_url(ev)
                # Pick first image if available
                imgs = ev.get("images", [])
                img_url = ""
                if isinstance(imgs, list) and imgs:
                    img = imgs[0] or {}
                    img_url = img.get("url") or ""
                # Price range
                pr = ev.get("priceRanges", [])
                pmin = None
                pmax = None
                curr = ""
                if isinstance(pr, list) and pr:
                    p0 = pr[0] or {}
                    try:
                        if p0.get("min") is not None:
                            pmin = float(p0.get("min"))
                        if p0.get("max") is not None:
                            pmax = float(p0.get("max"))
                    except Exception:
                        pass
                    curr = p0.get("currency") or ""
                out.append(Event(title=name, date=dt, location=loc, latitude=vlat, longitude=vlon, url=tm_url, source="Ticketmaster", image_url=img_url, price_min=pmin, price_max=pmax, currency=curr))
        # Fetch remaining pages concurrently
        if total_pages > 1:
            def fetch_page(p: int) -> List[Dict]:
                r = requests.get(url, params={**params_base, "page": p}, timeout=12)
                if r.status_code in (401, 403):
                    raise ValueError("Ticketmaster API key is invalid or unauthorized.")
                if r.status_code != 200:
                    return []
                d = r.json()
                return d.get("_embedded", {}).get("events", [])
            max_workers = min(8, total_pages)
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = {ex.submit(fetch_page, p): p for p in range(1, total_pages)}
                for fut in as_completed(futures):
                    try:
                        items = fut.result()
                        for ev in items:
                            name = ev.get("name") or "Ticketmaster Event"
                            ds = ev.get("dates", {}).get("start", {})
                            dt_text = ds.get("dateTime") or ds.get("localDate")
                            if not dt_text:
                                continue
                            try:
                                dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
                            except Exception:
                                try:
                                    dt = datetime.strptime(dt_text[:10], "%Y-%m-%d")
                                except Exception:
                                    continue
                            dt = _to_local_naive(dt)
                            venue = (ev.get("_embedded", {}).get("venues", [{}])[0])
                            vlat = float(venue.get("location", {}).get("latitude", lat))
                            vlon = float(venue.get("location", {}).get("longitude", lon))
                            loc = venue.get("name") or ""
                            tm_url = _tm_event_url(ev)
                            # Pick first image if available
                            imgs = ev.get("images", [])
                            img_url = ""
                            if isinstance(imgs, list) and imgs:
                                img = imgs[0] or {}
                                img_url = img.get("url") or ""
                            # Price range
                            pr = ev.get("priceRanges", [])
                            pmin = None
                            pmax = None
                            curr = ""
                            if isinstance(pr, list) and pr:
                                p0 = pr[0] or {}
                                try:
                                    if p0.get("min") is not None:
                                        pmin = float(p0.get("min"))
                                    if p0.get("max") is not None:
                                        pmax = float(p0.get("max"))
                                except Exception:
                                    pass
                                curr = p0.get("currency") or ""
                            out.append(Event(title=name, date=dt, location=loc, latitude=vlat, longitude=vlon, url=tm_url, source="Ticketmaster", image_url=img_url, price_min=pmin, price_max=pmax, currency=curr))
                    except Exception:
                        continue
        return out
    except Exception:
        return []


def fetch_eventbrite_events(lat: float, lon: float, radius_miles: float, start_date: datetime, end_date: datetime, api_key: Optional[str]) -> List[Event]:
    """Fetch events from Eventbrite API within a lat/lon + radius and date range.

    - Uses events search with venue/logo expansion
    - Attempts to fetch ticket classes to derive price ranges when available
    """
    token = api_key or DEFAULT_EB_API_KEY
    try:
        base = "https://www.eventbriteapi.com/v3"
        search_url = f"{base}/events/search/"
        headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
        out: List[Event] = []
        page = 1
        page_count = 1
        params_base = {
            "location.latitude": lat,
            "location.longitude": lon,
            "location.within": f"{max(1, int(round(radius_miles)))}mi",
            "expand": "venue,logo",
            "sort_by": "date",
            "start_date.range_start": _to_eb_iso(start_date),
            "start_date.range_end": _to_eb_iso(end_date + timedelta(days=1)),
        }
        r0 = requests.get(search_url, headers=headers, params={**params_base, "page": page}, timeout=14)
        if r0.status_code == 401:
            raise ValueError("Eventbrite API key is invalid or unauthorized.")
        if r0.status_code != 200:
            return []
        d0 = r0.json()
        events0 = d0.get("events", [])
        pagination = d0.get("pagination", {})
        page_count = int(pagination.get("page_count", 1)) or 1

        def _price_for_event(evt_id: str) -> Tuple[Optional[float], Optional[float], str]:
            try:
                tc_url = f"{base}/events/{evt_id}/ticket_classes/"
                tr = requests.get(tc_url, headers=headers, timeout=10)
                if tr.status_code != 200:
                    return (None, None, "")
                td = tr.json()
                classes = td.get("ticket_classes", [])
                prices: List[float] = []
                currency = ""
                for c in classes:
                    # skip free/donation tickets
                    if c.get("free") or c.get("donation"):
                        continue
                    cost = c.get("cost") or {}
                    mv = cost.get("major_value")
                    if mv is not None:
                        try:
                            prices.append(float(mv))
                            currency = cost.get("currency") or currency
                        except Exception:
                            pass
                if prices:
                    return (min(prices), max(prices), currency)
                return (None, None, "")
            except Exception:
                return (None, None, "")

        def _coerce_latlon(v: Dict) -> Tuple[float, float]:
            try:
                vlat = float(v.get("latitude", lat))
                vlon = float(v.get("longitude", lon))
                return vlat, vlon
            except Exception:
                return lat, lon

        def _process_events(items: List[Dict]):
            for ev in items:
                try:
                    name = (ev.get("name", {}) or {}).get("text") or "Eventbrite Event"
                    ds = ev.get("start", {}) or {}
                    dt_text = ds.get("utc") or ds.get("local")
                    if not dt_text:
                        continue
                    try:
                        dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
                    except Exception:
                        try:
                            dt = datetime.strptime(dt_text[:10], "%Y-%m-%d")
                        except Exception:
                            continue
                    dt = _to_local_naive(dt)
                    venue = (ev.get("venue") or {})
                    vlat, vlon = _coerce_latlon(venue)
                    loc = venue.get("name") or (venue.get("address", {}) or {}).get("localized_address_display", "")
                    url = (ev.get("url") or "").strip()
                    logo = (ev.get("logo") or {})
                    image_url = logo.get("url") or ""
                    evt_id = (ev.get("id") or "").strip()
                    pmin, pmax, curr = _price_for_event(evt_id) if evt_id else (None, None, "")
                    out.append(Event(title=name, date=dt, location=loc, latitude=vlat, longitude=vlon, url=url, source="Eventbrite", image_url=image_url, price_min=pmin, price_max=pmax, currency=curr))
                except Exception:
                    continue

        _process_events(events0)
        for p in range(2, page_count + 1):
            rp = requests.get(search_url, headers=headers, params={**params_base, "page": p}, timeout=14)
            if rp.status_code != 200:
                break
            dp = rp.json()
            _process_events(dp.get("events", []))
        return out
    except Exception:
        return []


def aggregate_events(zip_code: str, radius_miles: float, start_date: datetime, end_date: datetime, tm_key: Optional[str]) -> List[Event]:
    coords = geocode_zip(zip_code)
    if not coords:
        return []
    lat, lon = coords
    # Ticketmaster and Eventbrite
    tm = fetch_ticketmaster_events(lat, lon, radius_miles, start_date, end_date, tm_key)
    eb = fetch_eventbrite_events(lat, lon, radius_miles, start_date, end_date, None)
    all_events: List[Event] = tm + eb

    # Deduplicate by title + day
    seen = set()
    uniq: List[Event] = []
    for e in all_events:
        key = (e.title.strip().lower()[:40], e.date.date())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return sorted(uniq, key=lambda x: x.date)
