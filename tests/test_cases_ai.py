import pytest
from datetime import datetime, timedelta

from services.library_service import (
    add_book_to_catalog,
    borrow_book_by_patron,
    return_book_by_patron,
    calculate_late_fee_for_book,
    search_books_in_catalog,
    get_patron_status_report
)

# ------------------------
# R1: Add Book To Catalog
# ------------------------

def test_add_book_success_minimal_title_author(mocker):
    mocker.patch("services.library_service.get_book_by_isbn", return_value=None)
    mocker.patch("services.library_service.insert_book", return_value=True)

    success, msg = add_book_to_catalog("Z", "K", "1234567890123", 2)
    assert success is True
    assert "success" in msg.lower()


def test_add_book_fail_title_all_spaces():
    success, msg = add_book_to_catalog("    ", "Some Author", "9876543210987", 1)
    assert not success
    assert "title" in msg.lower()


def test_add_book_fail_author_too_long():
    long_author = "A" * 101
    success, msg = add_book_to_catalog("Valid Title", long_author, "1111111111111", 1)
    assert not success
    assert "author" in msg.lower()


def test_add_book_fail_isbn_length_short():
    success, msg = add_book_to_catalog("Book", "Author", "12345678", 1)
    assert not success
    assert "isbn" in msg.lower()


def test_add_book_fail_negative_copies():
    success, msg = add_book_to_catalog("Book", "Author", "2222222222222", -5)
    assert not success
    assert "positive" in msg.lower()


def test_add_book_fail_duplicate_isbn(mocker):
    # Patch to simulate duplicate ISBN
    mocker.patch("services.library_service.get_book_by_isbn", return_value={"id": 1})

    success, msg = add_book_to_catalog("Second Title", "Author Y", "5555555555555", 2)
    assert not success
    assert "already exists" in msg.lower()


# ------------------------
# R3: Borrow Book By Patron
# ------------------------

def test_borrow_success_valid_patron_and_book(mocker):
    fake_book = {"id": 1, "title": "X", "author": "Y",
                 "isbn": "111", "total_copies": 3, "available_copies": 1}

    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value=fake_book)
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    success, msg = borrow_book_by_patron("444444", 1)
    assert success is True


def test_borrow_fail_patron_id_invalid_length():
    success, msg = borrow_book_by_patron("12345", 1)
    assert success is False
    assert "patron" in msg.lower()


def test_borrow_fail_nonexistent_book(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value=None)

    success, msg = borrow_book_by_patron("123456", -1)
    assert not success
    assert "not found" in msg.lower()


def test_borrow_fail_unavailable_book(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 3, "title": "1984", "available_copies": 0})

    success, msg = borrow_book_by_patron("123456", 3)
    assert not success
    assert "not available" in msg.lower()


def test_borrow_fail_exceeding_limit(mocker):
    # Fake book always exists
    fake_book = {"id": 1, "title": "A", "author": "B",
                 "isbn": "111", "total_copies": 5, "available_copies": 5}

    mocker.patch("services.library_service.get_book_by_id", return_value=fake_book)
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    # Borrow count increases each time → hits limit on 6th
    mocker.patch("services.library_service.get_patron_borrow_count",
                 side_effect=[0, 1, 2, 3, 4, 5])

    for _ in range(5):
        borrow_book_by_patron("999999", 1)

    success, msg = borrow_book_by_patron("999999", 1)
    assert not success
    assert "limit" in msg.lower()


# ------------------------
# R4: Return Book By Patron
# ------------------------

def test_return_success_for_borrowed_book(mocker):
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "X", "available_copies": 0})
    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    success, msg = return_book_by_patron("888888", 1)
    assert success is True


def test_return_fail_invalid_patron_id_chars():
    success, msg = return_book_by_patron("12a456", 1)
    assert not success
    assert "invalid" in msg.lower()


def test_return_fail_not_borrowed_book(mocker):
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 9999, "title": "X", "available_copies": 1})
    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=False)

    success, msg = return_book_by_patron("777777", 9999)
    assert not success


def test_return_fail_double_return(mocker):
    # First borrow
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)
    borrow_book_by_patron("123123", 1)

    # First return succeeds
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "Book", "available_copies": 0})
    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=True)
    mocker.patch("services.library_service.update_book_availability",
                 return_value=True)
    assert return_book_by_patron("123123", 1)[0] is True

    # Second return fails
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=False)

    success, msg = return_book_by_patron("123123", 1)
    assert not success


def test_return_fail_nonexistent_book():
    success, msg = return_book_by_patron("123456", 9999)
    assert not success


# ------------------------
# R5: Late Fee Calculation
# ------------------------

def test_late_fee_returns_dict():
    fee = calculate_late_fee_for_book("111111", 1)
    assert isinstance(fee, dict)
    assert "fee_amount" in fee
    assert "days_overdue" in fee


def test_late_fee_amount_non_negative():
    fee = calculate_late_fee_for_book("222222", 1)
    assert fee["fee_amount"] >= 0


def test_late_fee_maximum_cap_not_exceeded():
    fee = calculate_late_fee_for_book("333333", 1)
    assert fee["fee_amount"] <= 15.00


# ------------------------
# R6: Book Search Functionality
# ------------------------

def test_search_title_partial_match_results(mocker):
    mocker.patch("services.library_service.get_all_books", return_value=[
        {"title": "Python Crash Course", "author": "A", "isbn": "1",
         "total_copies": 3, "available_copies": 1}
    ])
    results = search_books_in_catalog("python", "title")
    assert isinstance(results, list)


def test_search_author_partial_match_results(mocker):
    mocker.patch("services.library_service.get_all_books", return_value=[
        {"title": "Book", "author": "Stephen King", "isbn": "1",
         "total_copies": 3, "available_copies": 1}
    ])
    results = search_books_in_catalog("king", "author")
    assert isinstance(results, list)


def test_search_isbn_exact_match(mocker):
    mocker.patch("services.library_service.get_all_books", return_value=[
        {"title": "X", "author": "Y", "isbn": "9781234567897",
         "total_copies": 3, "available_copies": 1}
    ])
    results = search_books_in_catalog("9781234567897", "isbn")
    assert isinstance(results, list)


def test_search_no_results_for_unknown_term(mocker):
    mocker.patch("services.library_service.get_all_books", return_value=[])
    results = search_books_in_catalog("nonexistentbooktitle", "title")
    assert results == []


def test_search_invalid_search_type_returns_empty(mocker):
    mocker.patch("services.library_service.get_all_books", return_value=[])
    results = search_books_in_catalog("something", "unknown_type")
    assert results == []


# ------------------------
# R7: Patron Status Report
# ------------------------

def test_status_report_valid_patron_id(mocker):
    mocker.patch("services.library_service.get_patron_status_report",
                 return_value={"patron_id": "555555",
                               "borrowed_books": [],
                               "total_fees": 0,
                               "history": []})

    status = get_patron_status_report("555555")
    assert status["patron_id"] == "555555"


def test_status_report_invalid_patron_id_format():
    status = get_patron_status_report("abc123")
    assert status == {}


def test_status_report_empty_borrows_for_new_patron(mocker):
    mocker.patch("services.library_service.get_patron_status_report",
                 return_value={"borrowed_books": []})

    status = get_patron_status_report("000000")
    assert isinstance(status["borrowed_books"], list)


def test_status_report_borrowed_books_due_dates_format(mocker):
    mocker.patch(
        "services.library_service.get_patron_status_report",
        return_value={
            "borrowed_books": [{"due_date": "2025-11-20"}]
        }
    )

    status = get_patron_status_report("111111")
    due_date = status["borrowed_books"][0]["due_date"]
    assert isinstance(due_date, str)
    assert len(due_date) == 10  # YYYY-MM-DD
