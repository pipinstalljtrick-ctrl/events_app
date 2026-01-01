import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

import requests
from geopy.geocoders import Nominatim
import geopy.distance
from concurrent.futures import ThreadPoolExecutor, as_completed


# Backend default for Ticketmaster API key (used if none is provided)
DEFAULT_TM_API_KEY = "VHANTNxOcGFfpUD3k3whDbU1TiqBfbGs"
DEFAULT_EB_TOKEN = "ZUT6K5LOUUFZOFBRYXBY"

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

def _to_utc_iso(dt: datetime) -> str:
    """Generic ISO8601 UTC with trailing 'Z' for Eventbrite."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def fetch_eventbrite_events(zip_code: str, lat: float, lon: float, radius_miles: float, start_date: datetime, end_date: datetime, eb_token: Optional[str]) -> List[Event]:
    """Fetch Eventbrite events within radius and date range, expanded with venue.

    Authentication: Bearer token (private token).
    Pagination: page_count pages; fetch concurrently.
    """
    token = eb_token or DEFAULT_EB_TOKEN
    try:
        url = "https://www.eventbriteapi.com/v3/events/search/"
        out: List[Event] = []
        headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
        params_base = {
            "location.address": zip_code,
            "location.latitude": f"{lat}",
            "location.longitude": f"{lon}",
            "location.within": f"{int(round(radius_miles))}mi",
            "start_date.range_start": _to_utc_iso(start_date),
            "start_date.range_end": _to_utc_iso(end_date + timedelta(days=1)),
            "expand": "venue",
            "page": 1,
            "page_size": 200,
            "sort_by": "date",
        }
        r0 = requests.get(url, headers=headers, params=params_base, timeout=12)
        if r0.status_code in (401, 403):
            raise ValueError("Eventbrite API token is invalid or unauthorized.")
        if r0.status_code != 200:
            return []
        d0 = r0.json()
        ev0 = d0.get("events", [])
        pag = d0.get("pagination", {})
        page_count = int(pag.get("page_count", 1) or 1)

        def _parse_event(ev: Dict) -> Optional[Event]:
            try:
                name = (ev.get("name", {}) or {}).get("text") or "Eventbrite Event"
                ds = ev.get("start", {}) or {}
                dt_text = ds.get("utc") or ds.get("local")
                if not dt_text:
                    return None
                try:
                    dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
                except Exception:
                    return None
                dt = _to_local_naive(dt)
                venue = ev.get("venue") or {}
                vlat = float(venue.get("latitude", lat)) if venue.get("latitude") else lat
                vlon = float(venue.get("longitude", lon)) if venue.get("longitude") else lon
                loc_name = venue.get("name") or (venue.get("address", {}) or {}).get("city") or ""
                url_ev = ev.get("url") or ""
                logo = ev.get("logo") or {}
                img_url = logo.get("url") or ""
                # Price info
                is_free = bool(ev.get("is_free"))
                currency = ev.get("currency") or ""
                pmin = 0.0 if is_free else None
                pmax = 0.0 if is_free else None
                return Event(
                    title=name,
                    date=dt,
                    location=loc_name,
                    latitude=vlat,
                    longitude=vlon,
                    url=url_ev,
                    source="Eventbrite",
                    image_url=img_url,
                    price_min=pmin,
                    price_max=pmax,
                    currency=currency,
                )
            except Exception:
                return None

        for ev in ev0:
            e = _parse_event(ev)
            if e:
                out.append(e)

        # Fetch remaining pages concurrently
        if page_count > 1:
            def fetch_page(p: int) -> List[Dict]:
                rp = requests.get(url, headers=headers, params={**params_base, "page": p}, timeout=12)
                if rp.status_code in (401, 403):
                    raise ValueError("Eventbrite API token is invalid or unauthorized.")
                if rp.status_code != 200:
                    return []
                return (rp.json() or {}).get("events", [])

            max_workers = min(8, page_count)
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = {ex.submit(fetch_page, p): p for p in range(2, page_count + 1)}
                for fut in as_completed(futures):
                    try:
                        items = fut.result()
                        for ev in items:
                            e = _parse_event(ev)
                            if e:
                                out.append(e)
                    except Exception:
                        continue
        return out
    except Exception:
        return []


def aggregate_events(zip_code: str, radius_miles: float, start_date: datetime, end_date: datetime, tm_key: Optional[str]) -> List[Event]:
    coords = geocode_zip(zip_code)
    if not coords:
        return []
    lat, lon = coords
    # Ticketmaster + Eventbrite
    tm = fetch_ticketmaster_events(lat, lon, radius_miles, start_date, end_date, tm_key)
    eb = fetch_eventbrite_events(zip_code, lat, lon, radius_miles, start_date, end_date, None)
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
