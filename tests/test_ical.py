import unittest
from datetime import datetime, timedelta, timezone

from src.nuri_assistant.schedule.ical import CalendarEvent, parse_ics

KST = timezone(timedelta(hours=9))
WIDE = (datetime(2026, 1, 1), datetime(2028, 1, 1))


def vevent(*lines):
    return "\r\n".join(["BEGIN:VEVENT", *lines, "END:VEVENT"])


def cal(*events):
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", *events, "END:VCALENDAR", ""])


def run(text, window=WIDE):
    return parse_ics(text, window[0], window[1], KST)


def starts(events):
    return [e.start for e in events]


def zoneinfo_has(name):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:
        return False


class BasicsTests(unittest.TestCase):
    def test_line_unfolding_and_lowercase_names(self):
        text = ("BEGIN:VCALENDAR\nbegin:vevent\nuid:1\nsummary:Hel\n lo wor\n\tld\n"
                "dtstart:20261120T150000\nend:vevent\nEND:VCALENDAR\n")
        events = run(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Hello world")
        self.assertEqual(events[0].start, datetime(2026, 11, 20, 15))

    def test_escapes_and_title_rules(self):
        e = run(cal(vevent("UID:1", r"SUMMARY:  A\, B\; C\\ D\nE\NF ", "DTSTART:20261120T150000")))[0]
        self.assertEqual(e.title, "A, B; C\\ D E F")
        e = run(cal(vevent("UID:2", "SUMMARY:   ", "DTSTART:20261120T150000")))[0]
        self.assertEqual(e.title, "(제목 없음)")
        e = run(cal(vevent("UID:3", "DTSTART:20261120T150000")))[0]
        self.assertEqual(e.title, "(제목 없음)")
        e = run(cal(vevent("UID:4", "SUMMARY:" + "가" * 200, "DTSTART:20261120T150000")))[0]
        self.assertEqual(len(e.title), 120)

    def test_all_day(self):
        e = run(cal(vevent("UID:1", "SUMMARY:X", "DTSTART;VALUE=DATE:20261225")))[0]
        self.assertEqual(e, CalendarEvent("1", "X", datetime(2026, 12, 25), True))
        e = run(cal(vevent("UID:2", "SUMMARY:Y", "DTSTART:20261226")))[0]
        self.assertTrue(e.all_day)

    def test_floating_and_utc(self):
        e = run(cal(vevent("UID:1", "SUMMARY:F", "DTSTART:20261120T150000")))[0]
        self.assertEqual(e.start, datetime(2026, 11, 20, 15))
        self.assertFalse(e.all_day)
        e = run(cal(vevent("UID:2", "SUMMARY:Z", "DTSTART:20261120T060000Z")))[0]
        self.assertEqual(e.start, datetime(2026, 11, 20, 15))

    def test_tzid_asia_seoul(self):
        e = run(cal(vevent("UID:1", "SUMMARY:S", "DTSTART;TZID=Asia/Seoul:20261120T150000")))[0]
        self.assertEqual(e.start, datetime(2026, 11, 20, 15))

    @unittest.skipUnless(zoneinfo_has("America/New_York"), "no tz data")
    def test_tzid_new_york_to_kst(self):
        e = run(cal(vevent("UID:1", "SUMMARY:N", "DTSTART;TZID=America/New_York:20261120T090000")))[0]
        self.assertEqual(e.start, datetime(2026, 11, 20, 23))

    def test_unknown_tzid_falls_back_to_local(self):
        e = run(cal(vevent("UID:1", "SUMMARY:M", "DTSTART;TZID=Mars/Olympus:20261120T090000")))[0]
        self.assertEqual(e.start, datetime(2026, 11, 20, 9))

    def test_cancelled_excluded(self):
        text = cal(vevent("UID:1", "SUMMARY:A", "STATUS:CANCELLED", "DTSTART:20261120T150000"),
                   vevent("UID:2", "SUMMARY:B", "STATUS:CONFIRMED", "DTSTART:20261120T160000"))
        self.assertEqual([e.title for e in run(text)], ["B"])

    def test_valarm_and_vtodo_ignored(self):
        text = cal(
            vevent("UID:1", "SUMMARY:Real", "DTSTART:20261120T150000",
                   "BEGIN:VALARM", "SUMMARY:Alarm", "DTSTART:20200101T000000",
                   "ACTION:DISPLAY", "END:VALARM"),
            "BEGIN:VTODO", "UID:t", "SUMMARY:Todo", "DTSTART:20261121T100000", "END:VTODO")
        events = run(text)
        self.assertEqual([(e.title, e.start) for e in events], [("Real", datetime(2026, 11, 20, 15))])

    def test_empty_and_non_calendar(self):
        self.assertEqual(run(""), [])
        self.assertEqual(run("hello world"), [])
        self.assertEqual(run(vevent("UID:1", "DTSTART:20261120T150000")), [])
        self.assertEqual(parse_ics(None, *WIDE, KST), [])

    def test_broken_vevent_skipped(self):
        text = cal(vevent("UID:1", "SUMMARY:Bad", "DTSTART:garbage"),
                   vevent("UID:2", "SUMMARY:NoStart"),
                   "BEGIN:VEVENT", "UID:4", "SUMMARY:Unclosed", "DTSTART:20261121T150000",
                   vevent("UID:3", "SUMMARY:Good", "DTSTART:20261120T150000"))
        self.assertEqual([e.title for e in run(text)], ["Good"])

    def test_window_bounds(self):
        text = cal(vevent("UID:1", "SUMMARY:In", "DTSTART:20261120T100000"),
                   vevent("UID:2", "SUMMARY:Out", "DTSTART:20261121T100000"),
                   vevent("UID:0", "SUMMARY:Before", "DTSTART:20261119T235959"))
        w = (datetime(2026, 11, 20, 10), datetime(2026, 11, 21, 10))
        self.assertEqual([e.title for e in run(text, w)], ["In"])

    def test_sorted_and_deduplicated(self):
        a = vevent("UID:a", "SUMMARY:A", "DTSTART:20261122T100000")
        b = vevent("UID:b", "SUMMARY:B", "DTSTART:20261120T100000")
        events = run(cal(a, b, a))
        self.assertEqual([e.title for e in events], ["B", "A"])


class RecurrenceTests(unittest.TestCase):
    def test_daily_count(self):
        text = cal(vevent("UID:1", "SUMMARY:D", "DTSTART:20261110T090000", "RRULE:FREQ=DAILY;COUNT=3"))
        self.assertEqual(starts(run(text)), [datetime(2026, 11, d, 9) for d in (10, 11, 12)])

    def test_count_includes_occurrences_before_window(self):
        text = cal(vevent("UID:1", "SUMMARY:D", "DTSTART:20261101T090000", "RRULE:FREQ=DAILY;COUNT=5"))
        w = (datetime(2026, 11, 4), datetime(2026, 12, 1))
        self.assertEqual(starts(run(text, w)), [datetime(2026, 11, d, 9) for d in (4, 5)])

    def test_infinite_stops_at_window_end(self):
        text = cal(vevent("UID:1", "SUMMARY:D", "DTSTART:20261110T090000", "RRULE:FREQ=DAILY"))
        w = (datetime(2026, 11, 12), datetime(2026, 11, 17))
        self.assertEqual(len(run(text, w)), 5)

    def test_weekly_byday_interval(self):
        text = cal(vevent("UID:1", "SUMMARY:W", "DTSTART:20261102T100000",
                          "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR;COUNT=6"))
        days = [(e.start.month, e.start.day) for e in run(text)]
        self.assertEqual(days, [(11, 2), (11, 4), (11, 6), (11, 16), (11, 18), (11, 20)])

    def test_weekly_default_weekday(self):
        text = cal(vevent("UID:1", "SUMMARY:W", "DTSTART:20261104T100000", "RRULE:FREQ=WEEKLY;COUNT=3"))
        self.assertEqual([e.start.day for e in run(text)], [4, 11, 18])

    def test_monthly_31_skips_short_months(self):
        text = cal(vevent("UID:1", "SUMMARY:M", "DTSTART:20261031T100000", "RRULE:FREQ=MONTHLY;COUNT=3"))
        self.assertEqual(starts(run(text)), [datetime(2026, 10, 31, 10), datetime(2026, 12, 31, 10),
                                              datetime(2027, 1, 31, 10)])

    def test_monthly_last_friday(self):
        text = cal(vevent("UID:1", "SUMMARY:M", "DTSTART:20261030T100000",
                          "RRULE:FREQ=MONTHLY;BYDAY=-1FR;COUNT=3"))
        self.assertEqual([(e.start.month, e.start.day) for e in run(text)], [(10, 30), (11, 27), (12, 25)])

    def test_monthly_second_tuesday(self):
        text = cal(vevent("UID:1", "SUMMARY:M", "DTSTART:20261013T100000",
                          "RRULE:FREQ=MONTHLY;BYDAY=2TU;COUNT=3"))
        self.assertEqual([(e.start.month, e.start.day) for e in run(text)], [(10, 13), (11, 10), (12, 8)])

    def test_monthly_bymonthday(self):
        text = cal(vevent("UID:1", "SUMMARY:M", "DTSTART:20261101T100000",
                          "RRULE:FREQ=MONTHLY;BYMONTHDAY=1,15;COUNT=4"))
        self.assertEqual([(e.start.month, e.start.day) for e in run(text)],
                         [(11, 1), (11, 15), (12, 1), (12, 15)])

    def test_yearly_feb_29(self):
        text = cal(vevent("UID:1", "SUMMARY:Y", "DTSTART;VALUE=DATE:20240229", "RRULE:FREQ=YEARLY"))
        w = (datetime(2024, 1, 1), datetime(2033, 1, 1))
        self.assertEqual(starts(run(text, w)),
                         [datetime(2024, 2, 29), datetime(2028, 2, 29), datetime(2032, 2, 29)])

    def test_until_boundary_inclusive(self):
        base = ["UID:1", "SUMMARY:U", "DTSTART:20261110T090000"]
        # 2026-11-12T00:00:00Z is exactly 09:00 KST on the 12th
        text = cal(vevent(*base, "RRULE:FREQ=DAILY;UNTIL=20261112T000000Z"))
        self.assertEqual([e.start.day for e in run(text)], [10, 11, 12])
        text = cal(vevent(*base, "RRULE:FREQ=DAILY;UNTIL=20261111T235959Z"))
        self.assertEqual([e.start.day for e in run(text)], [10, 11])
        text = cal(vevent(*base, "RRULE:FREQ=DAILY;UNTIL=20261112"))
        self.assertEqual([e.start.day for e in run(text)], [10, 11, 12])

    def test_exdate_multiple_lines_and_lists(self):
        text = cal(vevent("UID:1", "SUMMARY:E", "DTSTART:20261110T090000", "RRULE:FREQ=DAILY;COUNT=6",
                          "EXDATE:20261111T090000,20261112T090000",
                          "EXDATE;TZID=Asia/Seoul:20261114T090000"))
        self.assertEqual([e.start.day for e in run(text)], [10, 13, 15])

    def test_exdate_date_and_utc_forms(self):
        text = cal(vevent("UID:1", "SUMMARY:E", "DTSTART;VALUE=DATE:20261110", "RRULE:FREQ=DAILY;COUNT=4",
                          "EXDATE;VALUE=DATE:20261111"),
                   vevent("UID:2", "SUMMARY:F", "DTSTART:20261110T090000Z", "RRULE:FREQ=DAILY;COUNT=3",
                          "EXDATE:20261111T090000Z"))
        got = [(e.uid, e.start.day) for e in run(text)]
        self.assertEqual(sorted(got), [("1", 10), ("1", 12), ("1", 13), ("2", 10), ("2", 12)])

    def test_recurrence_id_replaces_occurrence(self):
        text = cal(
            vevent("UID:a", "SUMMARY:Daily", "DTSTART:20261110T090000", "RRULE:FREQ=DAILY;COUNT=4"),
            vevent("UID:a", "SUMMARY:Moved", "RECURRENCE-ID:20261111T090000", "DTSTART:20261111T140000"),
            vevent("UID:a", "SUMMARY:Gone", "RECURRENCE-ID:20261112T090000", "STATUS:CANCELLED",
                   "DTSTART:20261112T090000"))
        got = [(e.title, e.start.day, e.start.hour) for e in run(text)]
        self.assertEqual(got, [("Daily", 10, 9), ("Moved", 11, 14), ("Daily", 13, 9)])

    def test_unsupported_freq_only_first(self):
        text = cal(vevent("UID:1", "SUMMARY:H", "DTSTART:20261110T090000", "RRULE:FREQ=HOURLY;COUNT=5"))
        self.assertEqual(len(run(text)), 1)
        text = cal(vevent("UID:2", "SUMMARY:H", "DTSTART:20261110T090000", "RRULE:nonsense"))
        self.assertEqual(len(run(text)), 1)

    @unittest.skipUnless(zoneinfo_has("America/New_York"), "no tz data")
    def test_weekly_keeps_wall_clock_across_dst(self):
        # US DST ends 2026-11-01: 15:00 New York is 05:00 KST (EDT) then 05:00+... -> 05:00 / 05:00 next day shift
        text = cal(vevent("UID:1", "SUMMARY:NY", "DTSTART;TZID=America/New_York:20261026T150000",
                          "RRULE:FREQ=WEEKLY;COUNT=2"))
        events = run(text)
        self.assertEqual(starts(events), [datetime(2026, 10, 27, 4), datetime(2026, 11, 3, 5)])


GOOGLE_SAMPLE = "\r\n".join([
    "BEGIN:VCALENDAR",
    "PRODID:-//Google Inc//Google Calendar 70.9054//EN",
    "VERSION:2.0",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Work",
    "X-WR-TIMEZONE:Asia/Seoul",
    "BEGIN:VTIMEZONE",
    "TZID:America/New_York",
    "X-LIC-LOCATION:America/New_York",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:-0500",
    "TZOFFSETTO:-0400",
    "TZNAME:EDT",
    "DTSTART:19700308T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:-0400",
    "TZOFFSETTO:-0500",
    "TZNAME:EST",
    "DTSTART:19701101T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
    "BEGIN:VEVENT",
    "DTSTART;TZID=Asia/Seoul:20261120T150000",
    "DTEND;TZID=Asia/Seoul:20261120T160000",
    "DTSTAMP:20261101T000000Z",
    "UID:abc123@google.com",
    "CREATED:20261001T000000Z",
    "DESCRIPTION:Line one\\nLine two",
    "LAST-MODIFIED:20261002T000000Z",
    "LOCATION:Room 1\\, 3F",
    "SEQUENCE:0",
    "STATUS:CONFIRMED",
    "SUMMARY:Team meeting",
    "TRANSP:OPAQUE",
    "BEGIN:VALARM",
    "ACTION:DISPLAY",
    "DESCRIPTION:This is an event reminder",
    "TRIGGER:-P0DT0H30M0S",
    "END:VALARM",
    "END:VEVENT",
    "BEGIN:VEVENT",
    "DTSTART;VALUE=DATE:20261225",
    "DTEND;VALUE=DATE:20261226",
    "UID:xmas@google.com",
    "STATUS:CONFIRMED",
    "SUMMARY:Christmas",
    "END:VEVENT",
    "END:VCALENDAR",
    "",
])


class GoogleSampleTests(unittest.TestCase):
    def test_timezone_block_not_mistaken_for_events(self):
        window = (datetime(1969, 1, 1), datetime(2040, 1, 1))
        events = run(GOOGLE_SAMPLE, window)
        self.assertEqual([(e.title, e.start, e.all_day) for e in events],
                         [("Team meeting", datetime(2026, 11, 20, 15), False),
                          ("Christmas", datetime(2026, 12, 25), True)])


class OldDailyEventTest(unittest.TestCase):
    def test_daily_event_started_many_years_ago_still_shows(self) -> None:
        text = "\r\n".join([
            "BEGIN:VCALENDAR", "BEGIN:VEVENT", "UID:old-daily", "SUMMARY:아침 운동",
            "DTSTART:20100301T070000", "RRULE:FREQ=DAILY", "END:VEVENT", "END:VCALENDAR",
        ])
        events = parse_ics(text, datetime(2026, 11, 12), datetime(2026, 11, 15), timezone(timedelta(hours=9)))
        self.assertEqual([e.start for e in events],
                         [datetime(2026, 11, 12, 7), datetime(2026, 11, 13, 7), datetime(2026, 11, 14, 7)])


if __name__ == "__main__":
    unittest.main()
