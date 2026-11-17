import logging

import pytest

from app.pii import MaskingFilter, install_log_masking, mask


@pytest.mark.parametrize(
    "text,label",
    [
        ("IC 900101-14-5678 here", "IC"),
        ("IC 900101145678 here", "IC"),
        ("IC 900101 14 5678 here", "IC"),
        ("card 4111 1111 1111 1111 ok", "CARD"),
        ("card 5500-0000-0000-0004 ok", "CARD"),
        ("call 012-345 6789 now", "PHONE"),
        ("call +60 11-2345 6789 now", "PHONE"),
        ("call 03-8888 1234 now", "PHONE"),
        ("mail a.b+c@example.com.my now", "EMAIL"),
        ("passport A12345678 now", "PASSPORT"),
        ("account 1620 4455 8891 now", "ACCOUNT"),
        ("ref 20261117884512 now", "ACCOUNT"),
    ],
)
def test_masks_each_type(text, label):
    masked, counts = mask(text)
    assert f"[{label}]" in masked
    assert counts == {label: 1}
    assert not any(ch.isdigit() for ch in masked.replace(label, ""))


@pytest.mark.parametrize("text", ["RM2,450 at 2.13am", "since 2021", "a 12-month plan, 5% cashback", "unit B-12-07", "RM320,000 over 30 years"])
def test_leaves_ordinary_numbers_alone(text):
    assert mask(text) == (text, {})


def test_invalid_date_is_not_an_ic_but_still_masked():
    masked, counts = mask("number 991345-14-5678")  # month 13 is impossible
    assert "IC" not in counts
    assert "991345" not in masked


def test_counts_hold_no_values():
    _, counts = mask("900101-14-5678 and 012-345 6789")
    assert counts == {"IC": 1, "PHONE": 1}


def test_log_filter_masks_records(caplog):
    logger = logging.getLogger("pii-test")
    logger.addFilter(MaskingFilter())
    with caplog.at_level(logging.INFO, logger="pii-test"):
        logger.info("customer %s called from %s", "900101-14-5678", "012-345 6789")
    assert "900101" not in caplog.text and "6789" not in caplog.text
    assert "[IC]" in caplog.text and "[PHONE]" in caplog.text


def test_global_masking_keeps_argument_positions_and_types():
    # Regression: uvicorn's access-log formatter reads record.args by index.
    install_log_masking()
    record = logging.getLogger("x").makeRecord("x", logging.INFO, __file__, 1, "%s - %s %d", ("900101-14-5678", "/q?ic=900101-14-5678", 200), None)
    assert record.args == ("[IC]", "/q?ic=[IC]", 200)
    assert record.getMessage() == "[IC] - /q?ic=[IC] 200"
