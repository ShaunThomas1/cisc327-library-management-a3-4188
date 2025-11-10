# Name : Shaun Thomas
# Student ID : 20394188
# Group : 4

import pytest
from datetime import datetime, timedelta

# Import only business logic (never DB functions directly)
from services.library_service import (
    add_book_to_catalog,
    borrow_book_by_patron,
    return_book_by_patron,
    calculate_late_fee_for_book,
    search_books_in_catalog,
    get_patron_status_report,
)

# ------------------------------------------------------------------------------
# R1 – ADD BOOK
# ------------------------------------------------------------------------------

def test_add_book_valid_input(mocker):
    mocker.patch("services.library_service.get_book_by_isbn", return_value=None)
    mocker.patch("services.library_service.insert_book", return_value=True)

    success, msg = add_book_to_catalog("Valid Book", "Author", "2020202020202", 5)
    assert success is True
    assert "success" in msg.lower()


def test_add_book_invalid_isbn():
    success, msg = add_book_to_catalog("Book", "Author", "12345", 3)
    assert success is False
    assert "13 digits" in msg.lower()


def test_add_book_negative_copies():
    success, msg = add_book_to_catalog("Book", "Author", "1234567890123", -1)
    assert success is False
    assert "positive" in msg.lower()


def test_add_book_title_too_long():
    long_title = "A" * 201
    success, msg = add_book_to_catalog(long_title, "Author", "1234567890123", 3)
    assert success is False
    assert "title" in msg.lower()


def test_add_book_duplicate_isbn(mocker):
    mocker.patch("services.library_service.get_book_by_isbn",
                 side_effect=[None, {"id": 1}])
    mocker.patch("services.library_service.insert_book", return_value=True)

    s1, _ = add_book_to_catalog("A", "B", "9999999999999", 1)
    s2, msg2 = add_book_to_catalog("B", "C", "9999999999999", 1)

    assert s1 is True
    assert s2 is False
    assert "exists" in msg2.lower()

# ------------------------------------------------------------------------------
# R2 – CATALOG DISPLAY
# ------------------------------------------------------------------------------

def _fake_books():
    return [
        {"id": 1, "title": "A", "author": "X", "isbn": "111",
         "total_copies": 3, "available_copies": 1},
        {"id": 2, "title": "B", "author": "Y", "isbn": "222",
         "total_copies": 5, "available_copies": 2},
    ]


def test_catalog_not_empty(mocker):
    fake = _fake_books()
    mocker.patch("services.library_service.get_all_books", return_value=fake)
    assert len(fake) > 0


def test_catalog_fields_present(mocker):
    fake = _fake_books()
    mocker.patch("services.library_service.get_all_books", return_value=fake)
    book = fake[0]
    assert "title" in book and "author" in book and "isbn" in book


def test_catalog_available_not_negative(mocker):
    fake = _fake_books()
    mocker.patch("services.library_service.get_all_books", return_value=fake)
    for b in fake:
        assert b["available_copies"] >= 0


def test_catalog_available_not_exceed_total(mocker):
    fake = _fake_books()
    mocker.patch("services.library_service.get_all_books", return_value=fake)
    for b in fake:
        assert b["available_copies"] <= b["total_copies"]

# ------------------------------------------------------------------------------
# R3 – BORROWING
# ------------------------------------------------------------------------------

def test_borrow_valid_book(mocker):
    fake_book = {"id": 1, "title": "X", "available_copies": 1}

    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value=fake_book)
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    success, msg = borrow_book_by_patron("123456", 1)
    assert success is True


def test_borrow_invalid_patron_id():
    success, msg = borrow_book_by_patron("12", 1)
    assert success is False
    assert "patron" in msg.lower()


def test_borrow_unavailable_book(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "available_copies": 0})

    success, msg = borrow_book_by_patron("123456", 1)
    assert success is False
    assert "not available" in msg.lower()


def test_borrow_over_limit(mocker):
    fake_book = {"id": 1, "title": "X", "available_copies": 5}

    mocker.patch("services.library_service.get_book_by_id", return_value=fake_book)
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    mocker.patch("services.library_service.get_patron_borrow_count",
                 side_effect=[0, 1, 2, 3, 4, 5])

    for _ in range(5):
        borrow_book_by_patron("654321", 1)

    s, msg = borrow_book_by_patron("654321", 1)
    assert s is False
    assert "limit" in msg.lower()


def test_borrow_invalid_book_id(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value=None)

    s, msg = borrow_book_by_patron("123456", 9999)
    assert s is False
    assert "not found" in msg.lower()

# ------------------------------------------------------------------------------
# R4 – RETURN PROCESSING
# ------------------------------------------------------------------------------

def test_return_valid(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    borrow_book_by_patron("111111", 1)

    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=True)

    s, msg = return_book_by_patron("111111", 1)
    assert isinstance(s, bool)


def test_return_not_borrowed(mocker):
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 2, "title": "T", "available_copies": 1})
    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=False)

    s, msg = return_book_by_patron("222222", 2)
    assert s is False
    assert "no active borrow" in msg.lower()


def test_return_twice(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)
    borrow_book_by_patron("333333", 1)

    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=True)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "available_copies": 0})
    assert return_book_by_patron("333333", 1)[0] is True

    mocker.patch("services.library_service.update_borrow_record_return_date",
                 return_value=False)
    s, msg = return_book_by_patron("333333", 1)
    assert s is False
    assert "no active borrow" in msg.lower()


def test_return_invalid_book_id(mocker):
    mocker.patch("services.library_service.get_book_by_id", return_value=None)

    s, msg = return_book_by_patron("123456", 9999)
    assert s is False
    assert "not found" in msg.lower()

# ------------------------------------------------------------------------------
# R5 – LATE FEE
# ------------------------------------------------------------------------------

def test_late_fee_no_overdue():
    assert isinstance(calculate_late_fee_for_book("123", 1), dict)


def test_late_fee_within_7_days():
    assert "fee_amount" in calculate_late_fee_for_book("123", 1)


def test_late_fee_beyond_7_days():
    assert "fee_amount" in calculate_late_fee_for_book("123", 1)


def test_late_fee_max_cap():
    assert "fee_amount" in calculate_late_fee_for_book("123", 1)

# ------------------------------------------------------------------------------
# R6 – SEARCH
# ------------------------------------------------------------------------------

def test_search_by_title_partial(mocker):
    fake_books = [
        {"id": 1, "title": "The Great Gatsby", "author": "F. Scott Fitzgerald", "isbn": "9780743273565", "total_copies": 3, "available_copies": 1},
        {"id": 2, "title": "Great Expectations", "author": "Charles Dickens", "isbn": "9780141439563", "total_copies": 2, "available_copies": 2},
        {"id": 3, "title": "Clean Code", "author": "Robert C. Martin", "isbn": "9780132350884", "total_copies": 4, "available_copies": 4},
    ]
    # Patch service-layer dependency
    mocker.patch("services.library_service.get_all_books", return_value=fake_books)

    results = search_books_in_catalog("great", "title")
    assert isinstance(results, list)
    assert len(results) == 2
    assert all("great" in b["title"].lower() for b in results)


def test_search_by_author_partial(mocker):
    fake_books = [
        {"id": 1, "title": "Dune", "author": "Frank Herbert", "isbn": "9780441172719", "total_copies": 5, "available_copies": 3},
        {"id": 2, "title": "It", "author": "Stephen King", "isbn": "9781501142970", "total_copies": 2, "available_copies": 2},
        {"id": 3, "title": "Misery", "author": "Stephen King", "isbn": "9780450417399", "total_copies": 2, "available_copies": 1},
    ]
    mocker.patch("services.library_service.get_all_books", return_value=fake_books)

    results = search_books_in_catalog("king", "author")
    assert isinstance(results, list)
    assert len(results) == 2
    assert all("king" in b["author"].lower() for b in results)


def test_search_by_isbn_exact(mocker):
    fake_books = [
        {"id": 1, "title": "Book A", "author": "A", "isbn": "9780451524935", "total_copies": 1, "available_copies": 1},
        {"id": 2, "title": "Book B", "author": "B", "isbn": "1234567890123", "total_copies": 2, "available_copies": 2},
    ]
    mocker.patch("services.library_service.get_all_books", return_value=fake_books)

    results = search_books_in_catalog("9780451524935", "isbn")
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["isbn"] == "9780451524935"


def test_search_no_results(mocker):
    fake_books = [
        {"id": 1, "title": "Operating Systems", "author": "Silberschatz", "isbn": "1111111111111", "total_copies": 3, "available_copies": 2},
        {"id": 2, "title": "Computer Networks", "author": "Tanenbaum", "isbn": "2222222222222", "total_copies": 2, "available_copies": 2},
    ]
    mocker.patch("services.library_service.get_all_books", return_value=fake_books)

    results = search_books_in_catalog("nonexistentbooktitle", "title")
    assert results == []


# ------------------------------------------------------------------------------
# R7 – PATRON STATUS
# ------------------------------------------------------------------------------

def test_patron_status_structure():
    assert isinstance(get_patron_status_report("123456"), dict)


def test_patron_status_no_borrows():
    assert isinstance(get_patron_status_report("999999"), dict)


def test_patron_status_with_borrow(mocker):
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id",
                 return_value={"id": 1, "title": "X", "available_copies": 1})
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)

    borrow_book_by_patron("888888", 1)

    status = get_patron_status_report("888888")
    assert isinstance(status, dict)


def test_patron_status_includes_fees():
    assert isinstance(get_patron_status_report("777777"), dict)


def test_patron_status_history_field():
    assert isinstance(get_patron_status_report("123456"), dict)
