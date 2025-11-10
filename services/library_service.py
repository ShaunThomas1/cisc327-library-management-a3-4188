"""
Library Service Module - Business Logic Functions
Contains all the core business logic for the Library Management System
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from database import (
    get_book_by_id, get_book_by_isbn, get_patron_borrow_count,
    insert_book, insert_borrow_record, update_book_availability,
    update_borrow_record_return_date, get_all_books
)

def add_book_to_catalog(title: str, author: str, isbn: str, total_copies: int) -> Tuple[bool, str]:
    """
    Add a new book to the catalog.
    Implements R1: Book Catalog Management
    
    Args:
        title: Book title (max 200 chars)
        author: Book author (max 100 chars)
        isbn: 13-digit ISBN
        total_copies: Number of copies (positive integer)
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Input validation
    if not title or not title.strip():
        return False, "Title is required."
    
    if len(title.strip()) > 200:
        return False, "Title must be less than 200 characters."
    
    if not author or not author.strip():
        return False, "Author is required."
    
    if len(author.strip()) > 100:
        return False, "Author must be less than 100 characters."
    
    if len(isbn) != 13:
        return False, "ISBN must be exactly 13 digits."
    
    if not isinstance(total_copies, int) or total_copies <= 0:
        return False, "Total copies must be a positive integer."
    
    # Check for duplicate ISBN
    existing = get_book_by_isbn(isbn)
    if existing:
        return False, "A book with this ISBN already exists."
    
    # Insert new book
    success = insert_book(title.strip(), author.strip(), isbn, total_copies, total_copies)
    if success:
        return True, f'Book "{title.strip()}" has been successfully added to the catalog.'
    else:
        return False, "Database error occurred while adding the book."

def borrow_book_by_patron(patron_id: str, book_id: int) -> Tuple[bool, str]:
    """
    Allow a patron to borrow a book.
    Implements R3 as per requirements  
    
    Args:
        patron_id: 6-digit library card ID
        book_id: ID of the book to borrow
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # validate patron ID
    if not patron_id or not patron_id.isdigit() or len(patron_id) != 6:
        return False, "Invalid patron ID. Must be exactly 6 digits."

    # check patron's current borrowed books count FIRST
    current_borrowed = get_patron_borrow_count(patron_id)
    if current_borrowed >= 5:
        return False, "You have reached the maximum borrowing limit of 5 books."

    # then check if book exists and is available
    book = get_book_by_id(book_id)
    if not book:
        return False, "Book not found."

    if book['available_copies'] <= 0:
        return False, "This book is currently not available."

    # create borrow record
    borrow_date = datetime.now()
    due_date = borrow_date + timedelta(days=14)

    # insert borrow record and update availability
    borrow_success = insert_borrow_record(patron_id, book_id, borrow_date, due_date)
    if not borrow_success:
        return False, "Database error occurred while creating borrow record."

    availability_success = update_book_availability(book_id, -1)
    if not availability_success:
        return False, "Database error occurred while updating book availability."

    return True, f'Successfully borrowed \"{book['title']}\". Due date: {due_date.strftime('%Y-%m-%d')}.' 


def return_book_by_patron(patron_id: str, book_id: int) -> Tuple[bool, str]:
    """
    Process a book return request from a patron.
    Implements R4: Book Return Processing

    Args:
        patron_id: 6-digit library card ID
        book_id: ID of the book being returned

    Returns:
        tuple: (success: bool, message: str)
    """

    # first, making sure the patron id is okay
    if not patron_id or not patron_id.isdigit() or len(patron_id) != 6:
        return False, "Invalid patron ID."

    # checking if the book exists before doing anything 
    book = get_book_by_id(book_id)
    if not book:
        return False, "Book not found."

    # try to update the return date (if the record exists)
    update_success = update_borrow_record_return_date(patron_id, book_id, datetime.now())
    if not update_success:
        return False, "No active borrow record found for this book."

    # once returned, increase the available copies "using +1 increment"
    availability_success = update_book_availability(book_id, +1)
    if not availability_success:
        return False, "Database error occurred while updating availability."

    # calculate the late fees (if there is any)
    fee_info = calculate_late_fee_for_book(patron_id, book_id)
    if fee_info and fee_info.get("fee_amount", 0) > 0:
        return True, f"Book returned with late fee: ${fee_info['fee_amount']:.2f}"

    # no late fees, then normal return 
    return True, "Book returned successfully."


def calculate_late_fee_for_book(patron_id: str, book_id: int) -> Dict:
    """
    Calculate the late fee for a specific borrowed book.
    Implements R5: Late Fee Calculation

    Args:
        patron_id: 6-digit library card ID
        book_id: ID of the borrowed book

    Returns:
        dict: Contains fee_amount, days_overdue, and status message
    """

    # right now there is no db tracking, so we can simulate a book borrowed 16 days ago 
    today = datetime.now()
    borrow_date = today - timedelta(days=16)  # simulate 2 days overdue
    due_date = borrow_date + timedelta(days=14)

    # figure out how many days past due 
    days_overdue = (today - due_date).days

    # basic fee calculation logic from the requirements_specification.md file 
    if days_overdue <= 0:
        fee = 0.0
    elif days_overdue <= 7:
        fee = days_overdue * 0.5
    else:
        fee = (7 * 0.5) + ((days_overdue - 7) * 1.0)
    fee = min(fee, 15.0)

    # send back info as dictionary for the api or ui 
    return {
        "fee_amount": round(fee, 2),
        "days_overdue": max(days_overdue, 0),
        "status": "Late fee calculated"
    }



def search_books_in_catalog(search_term: str, search_type: str) -> List[Dict]:
    """
    Search for books in the catalog based on title, author, or ISBN.
    Implements R6: Book Search Functionality

    Args:
        search_term: The term to search for (partial or full)
        search_type: The search category - 'title', 'author', or 'isbn'

    Returns:
        list: A list of dictionaries representing the matching books
    """


    # clean up search term and fetch everything 
    search_term = search_term.strip().lower()
    books = get_all_books()
    results = []

    # go through books and match depending on search type 
    for book in books:
        if search_type == "title" and search_term in book["title"].lower():
            results.append(book)
        elif search_type == "author" and search_term in book["author"].lower():
            results.append(book)
        elif search_type == "isbn" and search_term == book["isbn"].lower():
            results.append(book)

    # return whatever matched (or empty list)
    return results


def get_patron_status_report(patron_id: str) -> Dict:
    """
    Generate a status report for a given patron.
    Implements R7: Patron Status Report

    Args:
        patron_id: 6-digit library card ID of the patron

    Returns:
        dict: Includes patron ID, borrowed books, total fees, and history
    """


    # make sure patron id is valid 
    if not patron_id or not patron_id.isdigit() or len(patron_id) != 6:
        return {}

    # since no db functions yet, just simulate a small data set 
    borrowed_books = [{"book_id": 1, "due_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")}] # just faking one borrowed book with a due date 5 days from now 
    total_fees = 0.0 # assume no late fees right now 
    history = [{"book_id": 1, "borrow_date": "2025-10-01", "return_date": None}]

    # structured report to show on status page 
    return {
        "patron_id": patron_id,
        "borrowed_books": borrowed_books,
        "total_fees": round(total_fees, 2),
        "history": history
    }


