"""
Personal research tickers (private/companies.md, git-ignored) never reach the
repository. Skipped where the private list does not exist, as in CI.
"""

import pytest

from scripts import check_private_tickers as guard

PRIVATE = guard.private_tickers()
needs_private_list = pytest.mark.skipif(not PRIVATE, reason="no private/companies.md here")


@needs_private_list
def test_no_private_ticker_is_a_test_company():
    assert guard.leaks_in_test_list(PRIVATE) == []


@needs_private_list
def test_no_tracked_file_names_a_private_ticker():
    assert guard.leaks_in_tracked_files(PRIVATE) == []


@needs_private_list
def test_no_commit_message_or_author_names_a_private_ticker():
    assert guard.leaks_in_history(PRIVATE) == []


# The guard itself, on made-up tickers.

TABLE = """\
| Ticker | Why |
|--------|-----|
| ZZZQ | personal |
| QX | personal |
"""


def test_tickers_are_read_from_the_first_table_column():
    assert guard.tickers_in_table(TABLE) == {"ZZZQ", "QX"}


@pytest.mark.parametrize(
    "text, found",
    [
        ("analysis of zzzq results", {"ZZZQ"}),  # long tickers match in any case
        ("results/ZZZQ_2026-10-15", {"ZZZQ"}),
        ("ZZZQX is another word", set()),
        ("qx in lower case", set()),  # short tickers match exactly only
        ("ticker QX.", {"QX"}),
    ],
)
def test_tickers_are_found_as_whole_words(text, found):
    assert guard.leaks_in_text({"ZZZQ", "QX"}, text) == found


def test_a_commit_message_with_a_private_ticker_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "private_tickers", lambda path=None: {"ZZZQ"})
    message = tmp_path / "msg"
    message.write_text("Analyze ZZZQ receivables", encoding="utf-8")
    assert guard.main(["--commit-msg", str(message)]) == 1
    message.write_text("Read receivables from extension concepts", encoding="utf-8")
    assert guard.main(["--commit-msg", str(message)]) == 0
