"""Tests reports."""

import json
import pathlib

import pytest
import whenever

import sandman_core.controls as controls
import sandman_core.reports as reports
import tests.test_time_util as test_time_util

_default_report_event_when = None
_default_report_event_info = {}


def _check_default_report_event(event: reports.ReportEvent) -> None:
    """Check that the report event has default values."""
    assert event.when == _default_report_event_when
    assert event.info == _default_report_event_info
    assert event.is_valid() == False


def test_report_event_initialization() -> None:
    """Test initializing report events."""
    event = reports.ReportEvent()
    _check_default_report_event(event)

    with pytest.raises(TypeError):
        event.when = ""
    _check_default_report_event(event)

    intended_time = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=29,
        hour=18,
        minute=59,
        second=59,
        tz="America/Chicago",
    )
    event.when = intended_time
    assert event.when == intended_time
    assert event.info == _default_report_event_info
    assert event.is_valid() == False

    with pytest.raises(TypeError):
        event.info = 1
    event.when = intended_time
    assert event.when == intended_time
    assert event.info == _default_report_event_info
    assert event.is_valid() == False

    intended_info: reports.ReportEventInfo = {
        "type": "control",
        "control": "test_control",
        "action": "up",
        "source": "voice",
    }
    event.info = intended_info
    assert event.when == intended_time
    assert event.info == intended_info
    assert event.is_valid() == True


_default_report_version = -1
_default_report_start = None


def _check_default_report(report: reports.Report) -> None:
    """Check that the report has default values."""
    assert report.version == _default_report_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False


def _check_expected_report_events(
    events: list[reports.ReportEvent],
    expected_events: list[reports.ReportEvent],
) -> None:
    """Check whether report events match expected values."""
    num_events = len(events)
    num_expected_events = len(expected_events)
    assert num_events == num_expected_events

    if num_events != num_expected_events:
        return

    for index in range(num_events):
        assert events[index] == expected_events[index]


def test_report_initialization() -> None:
    """Test initializing reports."""
    report = reports.Report()
    _check_default_report(report)

    with pytest.raises(TypeError):
        report.version = ""
    _check_default_report(report)

    with pytest.raises(ValueError):
        report.version = -2
    _check_default_report(report)

    expected_version = 3

    report.version = expected_version
    assert report.version == expected_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False

    with pytest.raises(TypeError):
        report.start = ""
    assert report.version == expected_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False

    start_time = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=29,
        hour=17,
        minute=0,
        second=0,
        tz="America/Chicago",
    )
    report.start = start_time
    assert report.version == expected_version
    assert report.start == start_time
    assert len(report.events) == 0
    assert report.is_valid() == True

    # Add some events.

    first_time = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=29,
        hour=18,
        minute=59,
        second=59,
        tz="America/Chicago",
    )
    first_info: reports.ReportEventInfo = {
        "type": "control",
        "control": "test_control",
        "action": "up",
        "source": "voice",
    }
    first_event = reports.ReportEvent()
    first_event.when = first_time
    first_event.info = first_info
    assert first_event.is_valid() == True

    report.append_event(first_event)
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [first_event])
    assert report.is_valid() == True

    second_time = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=29,
        hour=19,
        minute=59,
        second=59,
        tz="America/Chicago",
    )
    second_info: reports.ReportEventInfo = {
        "type": "routine",
        "routine": "wake",
        "action": "up",
    }
    second_event = reports.ReportEvent()
    second_event.when = second_time
    second_event.info = second_info
    assert second_event.is_valid() == True

    report.append_event(second_event)
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [first_event, second_event])
    assert report.is_valid() == True


def test_report_loading() -> None:
    """Test loading report files."""
    path: str = "tests/data/reports/"

    with pytest.raises(FileNotFoundError):
        report = reports.Report.parse_from_file(path + "a")

    # Empty files cannot be parsed.
    report = reports.Report.parse_from_file(path + "report_test_empty.rpt")
    _check_default_report(report)

    # Must have a valid header.
    report = reports.Report.parse_from_file(
        path + "report_test_invalid_header.rpt"
    )
    _check_default_report(report)

    report = reports.Report.parse_from_file(
        path + "report_test_missing_version.rpt"
    )
    _check_default_report(report)

    report = reports.Report.parse_from_file(
        path + "report_test_type_version.rpt"
    )
    _check_default_report(report)

    report = reports.Report.parse_from_file(
        path + "report_test_invalid_version.rpt"
    )
    _check_default_report(report)

    # Beyond this point we have valid versions.
    expected_version = 4

    report = reports.Report.parse_from_file(
        path + "report_test_missing_start.rpt"
    )
    assert report.version == expected_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False

    report = reports.Report.parse_from_file(
        path + "report_test_type_start.rpt"
    )
    assert report.version == expected_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False

    report = reports.Report.parse_from_file(
        path + "report_test_invalid_start.rpt"
    )
    assert report.version == expected_version
    assert report.start == _default_report_start
    assert len(report.events) == 0
    assert report.is_valid() == False

    # Now we are testing events.
    start_time = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=2,
        hour=17,
        minute=0,
        second=0,
        tz="America/Chicago",
    )

    time0 = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=2,
        hour=23,
        minute=44,
        second=49,
        tz="America/Chicago",
    )

    time1 = whenever.ZonedDateTime(
        year=2026,
        month=3,
        day=2,
        hour=23,
        minute=44,
        second=50,
        tz="America/Chicago",
    )

    expected_event0 = reports.ReportEvent()
    expected_event0.when = time0
    expected_event0.info = {
        "type": "control",
        "control": "back",
        "action": "up",
        "source": "voice",
    }
    assert expected_event0.is_valid() == True

    expected_event1 = reports.ReportEvent()
    expected_event1.when = time1
    expected_event1.info = {
        "type": "control",
        "control": "back",
        "action": "down",
        "source": "voice",
    }
    assert expected_event1.is_valid() == True

    expected_events = [expected_event0, expected_event1]

    report = reports.Report.parse_from_file(
        path + "report_test_event_invalid.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_missing_when.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_type_when.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_invalid_when.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_missing_info.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_type_info.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_event_invalid_info.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, [expected_event1])
    assert report.is_valid() == True

    report = reports.Report.parse_from_file(
        path + "report_test_valid_events.rpt"
    )
    assert report.version == expected_version
    assert report.start == start_time
    _check_expected_report_events(report.events, expected_events)
    assert report.is_valid() == True


def _get_num_files_in_dir(path: pathlib.Path) -> int:
    """Get the number of files in a given directory."""
    num_files = 0

    for child in path.iterdir():
        if child.is_file():
            num_files += 1

    return num_files


def _check_file_and_read_lines(report_path: pathlib.Path) -> list[str]:
    """Check that a report file exists and read all of its lines."""
    report_exists = report_path.exists()
    assert report_exists == True

    lines = []

    if report_exists == False:
        return lines

    with open(str(report_path)) as file:
        lines = file.readlines()

    return lines


def test_report_file_creation(tmp_path: pathlib.Path) -> None:
    """Test the creation of report files."""
    reports_path = tmp_path / "reports/"
    reports.bootstrap_reports(str(tmp_path) + "/")
    assert reports_path.exists() == True

    time_source = test_time_util.TestTimeSource()

    assert _get_num_files_in_dir(reports_path) == 0
    report_manager = reports.ReportManager(time_source, str(tmp_path) + "/")

    # Processing should not result in any files being created, because the time
    # source doesn't have a valid time zone yet.
    assert _get_num_files_in_dir(reports_path) == 0
    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 0

    first_time = whenever.ZonedDateTime(
        year=2025,
        month=9,
        day=28,
        hour=16,
        minute=59,
        second=59,
        tz="America/Chicago",
    )
    time_source.set_current_time(first_time)
    assert time_source.get_current_time() == first_time

    # Processing should create an empty report file based on the current date.
    assert _get_num_files_in_dir(reports_path) == 0
    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 1

    # Check the file name and header.
    first_report_path = reports_path / "sandman2025-09-27.rpt"
    first_report_lines = _check_file_and_read_lines(first_report_path)

    assert len(first_report_lines) == 1

    header = json.loads(first_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    first_start_time = first_time.add(days=-1)
    first_start_time = first_start_time.replace_time(whenever.Time(17, 0))
    assert header["start"] == first_start_time.format_iso()

    # Processing again without changing time or adding events should not create
    # new files.
    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 1

    # Add one second to cross into the next report day.
    second_time = first_time.add(seconds=1)
    time_source.set_current_time(second_time)

    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 2

    # Check the file name and header.
    first_report_lines = _check_file_and_read_lines(first_report_path)

    assert len(first_report_lines) == 1

    header = json.loads(first_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION
    assert header["start"] == first_start_time.format_iso()

    second_report_path = reports_path / "sandman2025-09-28.rpt"
    second_report_lines = _check_file_and_read_lines(second_report_path)

    assert len(second_report_lines) == 1

    header = json.loads(second_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    second_start_time = second_time.replace_time(whenever.Time(17, 0))
    assert header["start"] == second_start_time.format_iso()


def test_report_events(tmp_path: pathlib.Path) -> None:
    """Test the addition of events to report files."""
    reports_path = tmp_path / "reports/"
    reports.bootstrap_reports(str(tmp_path) + "/")
    assert reports_path.exists() == True

    time_source = test_time_util.TestTimeSource()
    report_manager = reports.ReportManager(time_source, str(tmp_path) + "/")

    # Events should be ignored if there is no valid time zone.
    report_manager.add_status_event()

    first_time = whenever.ZonedDateTime(
        year=2025,
        month=9,
        day=28,
        hour=16,
        minute=59,
        second=59,
        tz="America/Chicago",
    )
    time_source.set_current_time(first_time)
    assert time_source.get_current_time() == first_time

    # Adding an event before processing does not cause a file to get created.
    report_manager.add_status_event()
    assert _get_num_files_in_dir(reports_path) == 0

    # Once processed, the event should show up in the appropriate file
    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 1

    first_report_path = reports_path / "sandman2025-09-27.rpt"
    first_report_lines = _check_file_and_read_lines(first_report_path)

    assert len(first_report_lines) == 2

    header = json.loads(first_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    first_event = json.loads(first_report_lines[1])
    first_event_time = whenever.ZonedDateTime.parse_iso(first_event["when"])
    assert first_event_time == first_time
    assert first_event["info"] == {"type": "status"}

    # Adding events that belong in different files, even out of order, will
    # put them in the correct files.
    second_time = first_time.add(seconds=1)
    time_source.set_current_time(second_time)
    report_manager.add_routine_event("wake", "start")

    time_source.set_current_time(first_time)
    report_manager.add_routine_event("wake", "stop")

    assert _get_num_files_in_dir(reports_path) == 1
    report_manager.process()
    assert _get_num_files_in_dir(reports_path) == 2

    first_report_lines = _check_file_and_read_lines(first_report_path)

    assert len(first_report_lines) == 3

    header = json.loads(first_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    first_event = json.loads(first_report_lines[1])
    first_event_time = whenever.ZonedDateTime.parse_iso(first_event["when"])
    assert first_event_time == first_time
    assert first_event["info"] == {"type": "status"}

    second_event = json.loads(first_report_lines[2])
    second_event_time = whenever.ZonedDateTime.parse_iso(second_event["when"])
    assert second_event_time == first_time
    assert second_event["info"] == {
        "type": "routine",
        "routine": "wake",
        "action": "stop",
    }

    # Check the second file.
    second_report_path = reports_path / "sandman2025-09-28.rpt"
    second_report_lines = _check_file_and_read_lines(second_report_path)

    assert len(second_report_lines) == 2

    header = json.loads(second_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    first_event = json.loads(second_report_lines[1])
    first_event_time = whenever.ZonedDateTime.parse_iso(first_event["when"])
    assert first_event_time == second_time
    assert first_event["info"] == {
        "type": "routine",
        "routine": "wake",
        "action": "start",
    }

    # Add some control events.
    third_time = second_time.add(seconds=5)
    time_source.set_current_time(third_time)
    control_name = "test_control"
    move_up_string = controls.Control.State.MOVE_UP.as_string()
    source_name = "test"
    report_manager.add_control_event(control_name, move_up_string, source_name)

    fourth_time = third_time.add(seconds=9)
    time_source.set_current_time(fourth_time)
    move_down_string = controls.Control.State.MOVE_DOWN.as_string()
    report_manager.add_control_event(
        control_name, move_down_string, source_name
    )

    second_report_lines = _check_file_and_read_lines(second_report_path)
    assert len(second_report_lines) == 2

    report_manager.process()
    second_report_lines = _check_file_and_read_lines(second_report_path)

    assert len(second_report_lines) == 4

    header = json.loads(second_report_lines[0])
    assert header["version"] == reports.ReportManager.REPORT_VERSION

    first_event = json.loads(second_report_lines[1])
    first_event_time = whenever.ZonedDateTime.parse_iso(first_event["when"])
    assert first_event_time == second_time
    assert first_event["info"] == {
        "type": "routine",
        "routine": "wake",
        "action": "start",
    }

    second_event = json.loads(second_report_lines[2])
    second_event_time = whenever.ZonedDateTime.parse_iso(second_event["when"])
    assert second_event_time == third_time
    assert second_event["info"] == {
        "type": "control",
        "control": control_name,
        "action": move_up_string,
        "source": source_name,
    }

    third_event = json.loads(second_report_lines[3])
    third_event_time = whenever.ZonedDateTime.parse_iso(third_event["when"])
    assert third_event_time == fourth_time
    assert third_event["info"] == {
        "type": "control",
        "control": control_name,
        "action": move_down_string,
        "source": source_name,
    }


def test_report_bootstrap(tmp_path: pathlib.Path) -> None:
    """Test report bootstrapping."""
    reports_path = tmp_path / "reports/"
    assert reports_path.exists() == False

    reports.bootstrap_reports(str(tmp_path) + "/")
    assert reports_path.exists() == True
