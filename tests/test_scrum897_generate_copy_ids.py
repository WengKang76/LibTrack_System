from datetime import datetime

import modules.book_catalogue.routes as book_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None
        return dict(self._data)


class FakeCopyDocumentReference:
    def __init__(self, records, document_id):
        self.records = records
        self.id = document_id

    def set(self, data):
        self.records[self.id] = dict(data)


class FakeCopiesCollection:
    def __init__(self, records):
        self.records = records

    def document(self, document_id):
        return FakeCopyDocumentReference(
            self.records,
            document_id,
        )


class FakeBookDocumentReference:
    def __init__(self, database, document_id):
        self.database = database
        self.id = document_id

    def collection(self, collection_name):
        assert collection_name == "copies"
        return FakeCopiesCollection(
            self.database.copies.setdefault(self.id, {})
        )


class FakeBookQuery:
    def __init__(
        self,
        database,
        field_name=None,
        expected_value=None,
        maximum_results=None,
    ):
        self.database = database
        self.field_name = field_name
        self.expected_value = expected_value
        self.maximum_results = maximum_results

    def where(self, field_name, operator, expected_value):
        assert operator == "=="
        return FakeBookQuery(
            self.database,
            field_name=field_name,
            expected_value=expected_value,
            maximum_results=self.maximum_results,
        )

    def limit(self, amount):
        return FakeBookQuery(
            self.database,
            field_name=self.field_name,
            expected_value=self.expected_value,
            maximum_results=amount,
        )

    def stream(self):
        snapshots = []

        for document_id, data in self.database.books.items():
            if (
                self.field_name is None
                or data.get(self.field_name) == self.expected_value
            ):
                snapshots.append(
                    FakeDocumentSnapshot(document_id, data)
                )

        if self.maximum_results is not None:
            snapshots = snapshots[: self.maximum_results]

        return snapshots


class FakeBooksCollection(FakeBookQuery):
    def __init__(self, database):
        super().__init__(database)

    def add(self, book_data):
        next_number = len(self.database.books) + 1
        book_id = f"BOOK{next_number:03d}"

        self.database.books[book_id] = dict(book_data)
        self.database.copies[book_id] = {}

        return (
            None,
            FakeBookDocumentReference(
                self.database,
                book_id,
            ),
        )


class FakeDatabase:
    def __init__(self):
        self.books = {}
        self.copies = {}

    def collection(self, collection_name):
        assert collection_name == "books"
        return FakeBooksCollection(self)


def valid_book_data(total_copies="3", isbn="9780000000001"):
    return {
        "title": "Python Programming",
        "author": "Sherman",
        "isbn": isbn,
        "category": "Programming",
        "publisher": "Technology Press",
        "publication_year": str(datetime.now().year),
        "total_copies": total_copies,
    }


def post_book(client, fake_database, monkeypatch, data=None, **kwargs):
    monkeypatch.setattr(book_routes, "db", fake_database)
    return client.post(
        "/books/add",
        data=data or valid_book_data(),
        **kwargs,
    )


def test_scrum_897_generates_exact_number_of_copy_records(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="3"),
    )

    assert response.status_code == 302
    assert len(fake_database.books) == 1
    assert len(fake_database.copies["BOOK001"]) == 3


def test_scrum_897_generates_sequential_zero_padded_copy_ids(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="3"),
    )

    assert list(fake_database.copies["BOOK001"].keys()) == [
        "COPY-BOOK001-001",
        "COPY-BOOK001-002",
        "COPY-BOOK001-003",
    ]


def test_scrum_897_copy_ids_are_unique(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="8"),
    )

    copy_ids = list(fake_database.copies["BOOK001"])

    assert len(copy_ids) == 8
    assert len(copy_ids) == len(set(copy_ids))


def test_scrum_897_each_copy_is_linked_to_correct_book(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(client, fake_database, monkeypatch)

    for copy_record in fake_database.copies["BOOK001"].values():
        assert copy_record["book_id"] == "BOOK001"


def test_scrum_897_each_copy_has_required_initial_fields(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(client, fake_database, monkeypatch)

    for expected_number, copy_record in enumerate(
        fake_database.copies["BOOK001"].values(),
        start=1,
    ):
        assert copy_record["copy_number"] == expected_number
        assert copy_record["status"] == "Available"
        assert copy_record["condition"] == "Good"
        assert copy_record["copy_id"].endswith(
            f"-{expected_number:03d}"
        )
        datetime.strptime(
            copy_record["created_at"],
            "%Y-%m-%d %H:%M:%S",
        )


def test_scrum_897_book_counts_match_generated_copy_count(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="5"),
    )

    saved_book = fake_database.books["BOOK001"]

    assert saved_book["total_copies"] == 5
    assert saved_book["available_copies"] == 5
    assert saved_book["status"] == "Available"
    assert len(fake_database.copies["BOOK001"]) == 5


def test_scrum_897_supports_single_copy_edge_case(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="1"),
    )

    assert list(fake_database.copies["BOOK001"]) == [
        "COPY-BOOK001-001"
    ]


def test_scrum_897_two_books_receive_separate_copy_namespaces(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="2", isbn="ISBN-001"),
    )
    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="2", isbn="ISBN-002"),
    )

    assert set(fake_database.copies["BOOK001"]) == {
        "COPY-BOOK001-001",
        "COPY-BOOK001-002",
    }
    assert set(fake_database.copies["BOOK002"]) == {
        "COPY-BOOK002-001",
        "COPY-BOOK002-002",
    }
    assert set(fake_database.copies["BOOK001"]).isdisjoint(
        fake_database.copies["BOOK002"]
    )


def test_scrum_897_success_message_reports_generated_quantity(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="4"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        b"Book record added successfully. "
        b"4 unique copy IDs were generated."
        in response.data
    )


def test_scrum_897_missing_quantity_creates_nothing(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()
    data = valid_book_data()
    data["total_copies"] = ""

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        data,
    )

    assert response.status_code == 400
    assert fake_database.books == {}
    assert fake_database.copies == {}


def test_scrum_897_non_numeric_quantity_creates_nothing(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="three"),
    )

    assert response.status_code == 400
    assert fake_database.books == {}
    assert fake_database.copies == {}


def test_scrum_897_zero_quantity_creates_nothing(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="0"),
    )

    assert response.status_code == 400
    assert fake_database.books == {}
    assert fake_database.copies == {}


def test_scrum_897_duplicate_isbn_creates_no_new_copies(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="2", isbn="DUPLICATE"),
    )

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        valid_book_data(total_copies="4", isbn="DUPLICATE"),
    )

    assert response.status_code == 400
    assert len(fake_database.books) == 1
    assert len(fake_database.copies) == 1
    assert len(fake_database.copies["BOOK001"]) == 2


def test_scrum_897_invalid_publication_year_creates_nothing(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()
    data = valid_book_data()
    data["publication_year"] = "year"

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        data,
    )

    assert response.status_code == 400
    assert fake_database.books == {}
    assert fake_database.copies == {}


def test_scrum_897_future_publication_year_creates_nothing(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()
    data = valid_book_data()
    data["publication_year"] = str(datetime.now().year + 1)

    response = post_book(
        client,
        fake_database,
        monkeypatch,
        data,
    )

    assert response.status_code == 400
    assert fake_database.books == {}
    assert fake_database.copies == {}
