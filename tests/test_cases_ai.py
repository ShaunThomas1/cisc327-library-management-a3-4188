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

from database import get_all_books


# ------------------------
# R1: Add Book To Catalog
# ------------------------

# older version
# def test_add_book_success_minimal_title_author():
#     # Minimal title (1 char), author (1 char), valid ISBN & copies
#     success, msg = add_book_to_catalog("Z", "K", "1234567890123", 2)
#     assert success is True
#     assert "success" in msg.lower()

# --- PATCH: replaces the original test_add_book_success_minimal_title_author ---
def test_add_book_success_minimal_title_author(mocker):
    mocker.patch("services.library_service.get_book_by_isbn", return_value=None)
    mocker.patch("services.library_service.insert_book", return_value=True)

    success, msg = add_book_to_catalog("Z", "K", "1234567890123", 2)
    assert success is True
    assert "success" in msg.lower()


def test_add_book_fail_title_all_spaces():
    # Title with spaces only counts as empty -> fail
    success, msg = add_book_to_catalog("    ", "Some Author", "9876543210987", 1)
    assert not success
    assert "title" in msg.lower()

def test_add_book_fail_author_too_long():
    # Author >100 chars should be rejected
    long_author = "A" * 101
    success, msg = add_book_to_catalog("Valid Title", long_author, "1111111111111", 1)
    assert not success
    assert "author" in msg.lower()

def test_add_book_fail_isbn_length_short():
    # Continue test with ISBN shorter than 13 digits
    success, msg = add_book_to_catalog("Book", "Author", "12345678", 1)
    assert not success
    assert "isbn" in msg.lower()

def test_add_book_fail_negative_copies():
    # Negative total copies not allowed
    success, msg = add_book_to_catalog("Book", "Author", "2222222222222", -5)
    assert not success
    assert "positive" in msg.lower()

def test_add_book_fail_duplicate_isbn():
    # Adding a book with existing ISBN should fail
    # You should ensure book with this ISBN exists in test DB before running this
    add_book_to_catalog("First Title", "Author X", "5555555555555", 3)
    success, msg = add_book_to_catalog("Second Title", "Author Y", "5555555555555", 2)
    assert not success
    assert "already exists" in msg.lower()

# ------------------------
# R3: Borrow Book By Patron
# ------------------------

def test_borrow_success_valid_patron_and_book():
    # Valid patron ID (6 digits) and book ID (assumes book id=1 exists and available)
    success, msg = borrow_book_by_patron("444444", 1)
    assert isinstance(success, bool)
    assert isinstance(msg, str)

def test_borrow_fail_patron_id_invalid_length():
    # Patron ID too short (5 digits) should fail
    success, msg = borrow_book_by_patron("12345", 1)
    assert success is False
    assert "patron" in msg.lower()

# older version
# def test_borrow_fail_nonexistent_book():
#     # Book ID that likely doesn't exist (-1)
#     success, msg = borrow_book_by_patron("123456", -1)
#     assert not success
#     assert "not found" in msg.lower()

# --- PATCH: replaces the original test_borrow_fail_nonexistent_book ---
def test_borrow_fail_nonexistent_book(mocker):
    # Ensuring the patron is not at limit; forces "book not found"
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value=None)

    success, msg = borrow_book_by_patron("123456", -1)
    assert not success
    assert "not found" in msg.lower()


# older version
# def test_borrow_fail_unavailable_book():
#     # If book with id=3 exists but has no available copies (set manually), should fail
#     success, msg = borrow_book_by_patron("123456", 3)
#     assert not success
#     assert "not available" in msg.lower()

# --- PATCH: replaces the original test_borrow_fail_unavailable_book ---
def test_borrow_fail_unavailable_book(mocker):
    # Ensure patron under limit; force available_copies = 0
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value={"id": 3, "title": "1984", "available_copies": 0})

    success, msg = borrow_book_by_patron("123456", 3)
    assert not success
    assert "not available" in msg.lower()



def test_borrow_fail_exceeding_limit():
    # Try to borrow when patron already has 5 books (use known patron or repeat)
    for _ in range(5):
        borrow_book_by_patron("999999", 1)
    success, msg = borrow_book_by_patron("999999", 2)
    assert not success
    assert "limit" in msg.lower()

# ------------------------
# R4: Return Book By Patron
# ------------------------

def test_return_success_for_borrowed_book():
    # First borrow then return book for a patron id
    borrow_book_by_patron("888888", 1)
    success, msg = return_book_by_patron("888888", 1)
    assert isinstance(success, bool)
    assert isinstance(msg, str)

def test_return_fail_invalid_patron_id_chars():
    # Patron ID contains letters → fail
    success, msg = return_book_by_patron("12a456", 1)
    assert not success
    assert "invalid" in msg.lower()

def test_return_fail_not_borrowed_book():
    # Return a book not borrowed by this patron
    success, msg = return_book_by_patron("777777", 9999)
    assert not success

# older version
# def test_return_fail_double_return():
#     # Return book twice causes second attempt to fail
#     borrow_book_by_patron("123123", 1)
#     return_book_by_patron("123123", 1)
#     success, msg = return_book_by_patron("123123", 1)
#     assert not success

# --- PATCH: replaces the original test_return_fail_double_return ---
def test_return_fail_double_return(mocker):
    # Borrow succeeds
    mocker.patch("services.library_service.get_patron_borrow_count", return_value=0)
    mocker.patch("services.library_service.get_book_by_id", return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.insert_borrow_record", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)
    borrow_book_by_patron("123123", 1)

    # First return succeeds
    mocker.patch("services.library_service.get_book_by_id", return_value={"id": 1, "title": "Book", "available_copies": 0})
    mocker.patch("services.library_service.update_borrow_record_return_date", return_value=True)
    mocker.patch("services.library_service.update_book_availability", return_value=True)
    assert return_book_by_patron("123123", 1)[0] is True

    # Second return fails (no active record)
    mocker.patch("services.library_service.get_book_by_id", return_value={"id": 1, "title": "Book", "available_copies": 1})
    mocker.patch("services.library_service.update_borrow_record_return_date", return_value=False)
    success, msg = return_book_by_patron("123123", 1)
    assert not success
    assert "no active borrow record" in msg.lower()

def test_return_fail_nonexistent_book():
    # Return book that does not exist in catalog
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

def test_search_title_partial_match_results():
    results = search_books_in_catalog("python", "title")
    assert isinstance(results, list)
    if results:
        assert any("python" in book["title"].lower() for book in results)

def test_search_author_partial_match_results():
    results = search_books_in_catalog("king", "author")
    assert isinstance(results, list)
    if results:
        assert any("king" in book["author"].lower() for book in results)

def test_search_isbn_exact_match():
    results = search_books_in_catalog("9781234567897", "isbn")
    assert isinstance(results, list)
    if results:
        assert all(book["isbn"] == "9781234567897" for book in results)

def test_search_no_results_for_unknown_term():
    results = search_books_in_catalog("nonexistentbooktitle", "title")
    assert results == []

def test_search_invalid_search_type_returns_empty():
    results = search_books_in_catalog("something", "unknown_type")
    assert results == []

# ------------------------
# R7: Patron Status Report
# ------------------------

def test_status_report_valid_patron_id():
    status = get_patron_status_report("555555")
    assert isinstance(status, dict)
    assert status.get("patron_id") == "555555"
    assert "borrowed_books" in status
    assert "total_fees" in status
    assert "history" in status

def test_status_report_invalid_patron_id_format():
    status = get_patron_status_report("abc123")
    assert status == {}

def test_status_report_empty_borrows_for_new_patron():
    # Assuming patron '000000' exists but hasn't borrowed
    status = get_patron_status_report("000000")
    if status:
        assert isinstance(status["borrowed_books"], list)
        assert len(status["borrowed_books"]) == 0 or status["borrowed_books"] is not None

def test_status_report_borrowed_books_due_dates_format():
    status = get_patron_status_report("111111")
    if status and status.get("borrowed_books"):
        due_date = status["borrowed_books"][0].get("due_date")
        assert isinstance(due_date, str)
        assert len(due_date) == 10  # YYYY-MM-DD