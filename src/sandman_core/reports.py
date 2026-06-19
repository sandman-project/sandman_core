"""Everything needed to support reports.

Reports are automatically generated based on activity.
"""

import collections
import json
import logging
import pathlib
import typing

import whenever

from . import time_util

_logger = logging.getLogger("sandman.report")


type ReportEventInfo = typing.Mapping[
    str, typing.Mapping[str, int | str] | int | str
]


class ReportEvent:
    """An event for a report file."""

    def __init__(self) -> None:
        """Initialize the report event."""
        self.__when: whenever.ZonedDateTime | None = None
        self.__info: ReportEventInfo = {}

    @property
    def when(self) -> whenever.ZonedDateTime | None:
        """Get the when."""
        return self.__when

    @when.setter
    def when(self, when: whenever.ZonedDateTime) -> None:
        """Set the when."""
        if isinstance(when, whenever.ZonedDateTime) == False:
            raise TypeError("When must be a zoned date/time.")

        self.__when = when

    @property
    def info(self) -> ReportEventInfo:
        """Get the info."""
        return self.__info

    @info.setter
    def info(self, info: ReportEventInfo) -> None:
        """Set the info."""
        if isinstance(info, dict) == False:
            raise TypeError("Info must be a ReportEventInfo.")

        # This will be more robust if the info is a concrete type.
        if info == {}:
            raise ValueError("Info must not be an empty dictionary.")

        self.__info = info

    def is_valid(self) -> bool:
        """Check whether this is a valid report event."""
        if self.__when is None:
            return False

        # This will be a lot more robust if the info becomes a concrete class.
        if self.__info == {}:
            return False

        return True

    def __eq__(self, other: object) -> bool:
        """Check whether this event and another have equal values."""
        if not isinstance(other, ReportEvent):
            return NotImplemented

        return (self.__when == other.__when) and (self.__info == other.__info)

    @classmethod
    def parse_from_string(
        cls, event_string: str, filename: str
    ) -> typing.Self:
        """Parse the event from a (JSON) string."""
        event = cls()

        try:
            event_json = json.loads(event_string)

        except json.JSONDecodeError:
            _logger.warning(
                "JSON error decoding event for report file '%s'.",
                filename,
            )
            return event

        try:
            event.when = whenever.ZonedDateTime.parse_iso(event_json["when"])

        except KeyError:
            _logger.warning(
                "Missing 'when' key in event in report file '%s'.",
                filename,
            )
            return event

        except (TypeError, ValueError):
            _logger.warning(
                "Invalid when '%s' in event in report file '%s'.",
                str(event_json["when"]),
                filename,
            )
            return event

        try:
            info = event_json["info"]

        except KeyError:
            _logger.warning(
                "Missing 'info' key in event in report file '%s'.",
                filename,
            )

        else:
            if isinstance(info, dict) == True:
                try:
                    event.info = dict(info)

                except ValueError:
                    _logger.warning(
                        "Invalid info '%s' in event in report file '%s'.",
                        str(info),
                        filename,
                    )

            else:
                _logger.warning(
                    "Invalid info '%s' in event in report file '%s'.",
                    str(info),
                    filename,
                )

        return event


class Report:
    """All of the information from a report file."""

    def __init__(self) -> None:
        """Initialize the report."""
        self.__version = -1
        self.__start: whenever.ZonedDateTime | None = None
        self.__events: list[ReportEvent] = []

    @property
    def version(self) -> int:
        """Get the version."""
        return self.__version

    @version.setter
    def version(self, version: int) -> None:
        """Set the version."""
        if isinstance(version, int) == False:
            raise TypeError("Version must be an integer.")

        if version < 0:
            raise ValueError("Cannot set a negative version.")

        self.__version = version

    @property
    def start(self) -> whenever.ZonedDateTime | None:
        """Get the start."""
        return self.__start

    @start.setter
    def start(self, start: whenever.ZonedDateTime) -> None:
        """Set the start."""
        if isinstance(start, whenever.ZonedDateTime) == False:
            raise TypeError("Start must be a zoned date/time.")

        self.__start = start

    @property
    def events(self) -> list[ReportEvent]:
        """Get the events."""
        return self.__events

    def append_event(self, event: ReportEvent) -> None:
        """Add an event to the end."""
        self.__events.append(event)

    def is_valid(self) -> bool:
        """Check whether this is a valid report."""
        if self.__version < 0:
            return False

        if self.__start is None:
            return False

        return True

    @classmethod
    def parse_from_file(cls, filename: str) -> typing.Self:
        """Parse a report from a file."""
        report = cls()

        try:
            with open(filename) as file:
                report_lines = file.readlines()

        except FileNotFoundError as error:
            _logger.error("Could not find report file '%s'.", filename)
            raise error

        num_lines = len(report_lines)

        if num_lines == 0:
            _logger.warning("Report file '%s' is empty.", filename)
            return report

        # The first line is expected to be the header.
        try:
            header_json = json.loads(report_lines[0])

        except json.JSONDecodeError:
            _logger.error(
                "JSON error decoding header for report file '%s'.",
                filename,
            )
            return report

        try:
            report.version = header_json["version"]

        except KeyError:
            _logger.error("Missing version in report file '%s'.", filename)
            return report

        except (TypeError, ValueError):
            _logger.error(
                "Invalid version '%s' in report file '%s'.",
                str(header_json["version"]),
                filename,
            )
            return report

        # Don't support loading reports older than version 4.
        if report.version < 4:
            return report

        try:
            report.start = whenever.ZonedDateTime.parse_iso(
                header_json["start"]
            )

        except KeyError:
            _logger.error("Missing start in report file '%s'.", filename)
            return report

        except (TypeError, ValueError):
            _logger.error(
                "Invalid start '%s' in report file '%s'.",
                str(header_json["start"]),
                filename,
            )
            return report

        # Load the events.
        for line_index in range(1, num_lines):
            event = ReportEvent.parse_from_string(
                report_lines[line_index], filename
            )

            if event.is_valid() == True:
                report.append_event(event)

        return report


class ReportManager:
    """Manages recording events into per day report files."""

    REPORT_VERSION = 4

    def __init__(
        self, time_source: time_util.TimeSource, base_dir: str
    ) -> None:
        """Initialize the instance."""
        self.__time_source = time_source
        self.__reports_dir = base_dir + "reports/"
        # Eventually this should be configurable.
        self.__report_start_hour = 17
        self.__pending_events = collections.deque[ReportEvent]()

    def process(self) -> None:
        """Process reports."""
        try:
            curr_time = self.__time_source.get_current_time()

        except Exception:
            _logger.warning(
                "The report manager cannot function without the current time."
            )
            return

        # Even if there are no events, we want to make sure that we are
        # creating empty report files.
        self.__maybe_create_report_file(curr_time)

        event = self.__pop_event()

        while event is not None:
            self.__write_event(event)

            event = self.__pop_event()

    def add_control_event(
        self, control: str, action: str, source: str
    ) -> None:
        """Add a control event at the current time."""
        info = {
            "type": "control",
            "control": control,
            "action": action,
            "source": source,
        }
        self.__add_event(info)

    def add_routine_event(self, routine: str, action: str) -> None:
        """Add a routine event at the current time."""
        info = {"type": "routine", "routine": routine, "action": action}
        self.__add_event(info)

    def add_status_event(self) -> None:
        """Add a status event at the current time."""
        info = {"type": "status"}
        self.__add_event(info)

    def __get_start_time_from_time(
        self, time: whenever.ZonedDateTime
    ) -> whenever.ZonedDateTime:
        """Get the appropriate start time based on the given time."""
        start_time = time

        if start_time.hour < self.__report_start_hour:
            start_time = start_time.add(days=-1)

        start_time = start_time.replace_time(
            whenever.Time(self.__report_start_hour)
        )
        return start_time

    def __get_report_name_from_time(self, time: whenever.ZonedDateTime) -> str:
        """Get the report name based on given time."""
        start_time = self.__get_start_time_from_time(time)

        return (
            f"sandman{start_time.year}-{start_time.month:02}-"
            + f"{start_time.day:02}"
        )

    def __maybe_create_report_file(self, time: whenever.ZonedDateTime) -> None:
        """Create the desired report if it doesn't exist."""
        report_name = self.__get_report_name_from_time(time)
        report_file_name = self.__reports_dir + report_name + ".rpt"

        report_path = pathlib.Path(report_file_name)

        if report_path.exists():
            return

        # Get the start time string for the header.
        start_time = self.__get_start_time_from_time(time)
        start_time_string = start_time.format_iso()

        header = {
            "version": self.REPORT_VERSION,
            "start": start_time_string,
        }
        header_line = json.dumps(header) + "\n"

        # Add the header.
        with open(report_file_name, "w", encoding="utf-8") as file:
            file.write(header_line)

        _logger.info("Created report file '%s'.", str(report_file_name))

    def __add_event(self, info: ReportEventInfo) -> None:
        """Add an event with the given info at the current time."""
        try:
            curr_time = self.__time_source.get_current_time()

        except Exception:
            _logger.warning("Cannot add events without a valid time.")
            return

        event = ReportEvent()
        event.when = curr_time
        event.info = info

        if event.is_valid() == False:
            _logger.warning("Try to add an invalid event %s.", str(event))
            return

        self.__pending_events.append(event)

    def __pop_event(self) -> ReportEvent | None:
        """Pop an event from the queue if there is one.

        Returns the event or None if the queue is empty.
        """
        try:
            event = self.__pending_events.popleft()

        except IndexError:
            return None

        return event

    def __write_event(self, event: ReportEvent) -> None:
        """Write the event to the appropriate file."""
        if event.when is None:
            return

        self.__maybe_create_report_file(event.when)

        report_name = self.__get_report_name_from_time(event.when)
        report_file_name = self.__reports_dir + report_name + ".rpt"

        report_path = pathlib.Path(report_file_name)

        if report_path.exists() == False:
            _logger.error(
                "Failed to add event to '%s' - file doesn't exist.",
                report_file_name,
            )
            return

        event_json = {
            "when": event.when.format_iso(),
            "info": event.info,
        }
        event_line = json.dumps(event_json) + "\n"

        with open(report_file_name, "a", encoding="utf-8") as file:
            file.write(event_line)


def bootstrap_reports(base_dir: str) -> None:
    """Handle bootstrapping for reports."""
    report_path = pathlib.Path(base_dir + "reports/")

    if report_path.exists() == True:
        return

    _logger.info("Creating missing report directory '%s'.", str(report_path))

    try:
        report_path.mkdir()

    except Exception:
        _logger.warning(
            "Failed to create report directory '%s'.", str(report_path)
        )
        return
