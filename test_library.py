"""
Tests for library module - book creation and chapter retrieval.
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

import library


@pytest.fixture
def temp_library(monkeypatch):
    """Create a temporary library directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    lib_dir = temp_dir / "library"
    data_dir = temp_dir / "data"

    lib_dir.mkdir()
    data_dir.mkdir()

    # Monkeypatch the library paths
    monkeypatch.setattr(library, 'LIBRARY_DIR', lib_dir)
    monkeypatch.setattr(library, 'DATA_DIR', data_dir)
    monkeypatch.setattr(library, 'LIBRARY_INDEX', data_dir / "library.json")

    # Initialize the library
    library.init_library()

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


class TestCreateBook:
    """Tests for library.create_book()"""

    def test_create_book_basic(self, temp_library):
        """Test creating a book with chapters."""
        chapters = [
            {'title': 'Introduction', 'content': 'Welcome to the book.', 'word_count': 4},
            {'title': 'Chapter 1', 'content': '# Chapter 1\n\nFirst chapter content.', 'word_count': 5},
            {'title': 'Chapter 2', 'content': '# Chapter 2\n\nSecond chapter content.', 'word_count': 5},
        ]

        book = library.create_book(
            title='Test Book',
            filename='test.md',
            chapters=chapters,
        )

        # Check book metadata
        assert book['type'] == 'book'
        assert book['title'] == 'Test Book'
        assert book['filename'] == 'test.md'
        assert book['chapter_count'] == 3
        assert book['total_words'] == 14
        assert 'id' in book
        assert 'created_at' in book
        assert 'content_hash' in book

    def test_create_book_stores_chapters(self, temp_library):
        """Test that chapters are stored correctly in metadata."""
        chapters = [
            {'title': 'Intro', 'content': 'Hello world.', 'word_count': 2},
            {'title': 'Main', 'content': '# Main\n\nContent here.', 'word_count': 4},
        ]

        book = library.create_book(
            title='My Book',
            filename='book.md',
            chapters=chapters,
        )

        # Get the full metadata
        full_book = library.get_item(book['id'])

        assert 'chapters' in full_book
        assert len(full_book['chapters']) == 2
        assert full_book['chapters'][0]['title'] == 'Intro'
        assert full_book['chapters'][0]['content'] == 'Hello world.'
        assert full_book['chapters'][0]['audio_path'] is None
        assert full_book['chapters'][1]['title'] == 'Main'

    def test_create_book_appears_in_index(self, temp_library):
        """Test that book appears in library index with correct summary."""
        chapters = [
            {'title': 'Ch1', 'content': 'Content.', 'word_count': 1},
        ]

        book = library.create_book(
            title='Indexed Book',
            filename='indexed.md',
            chapters=chapters,
        )

        # Check index
        items = library.get_all_items()
        assert len(items) == 1

        item = items[0]
        assert item['type'] == 'book'
        assert item['title'] == 'Indexed Book'
        assert item['chapter_count'] == 1
        assert item['total_words'] == 1
        assert item['word_count'] == 1  # For compatibility
        assert item['audio_generated'] == False

    def test_create_book_stores_document(self, temp_library):
        """Test that full document is stored as document.md."""
        chapters = [
            {'title': 'Part 1', 'content': 'First part.', 'word_count': 2},
            {'title': 'Part 2', 'content': 'Second part.', 'word_count': 2},
        ]

        book = library.create_book(
            title='Doc Book',
            filename='doc.md',
            chapters=chapters,
        )

        # Read the stored document
        content = library.get_document_content(book['id'])
        assert content == 'First part.\n\nSecond part.'

    def test_create_book_with_content_hash(self, temp_library):
        """Test creating book with pre-computed content hash."""
        chapters = [
            {'title': 'Ch1', 'content': 'Test content.', 'word_count': 2},
        ]

        # Pre-compute hash
        full_content = 'Test content.'
        content_hash = library.compute_content_hash(full_content)

        book = library.create_book(
            title='Hash Book',
            filename='hash.md',
            chapters=chapters,
            content_hash=content_hash,
        )

        assert book['content_hash'] == content_hash

    def test_create_book_can_be_deleted(self, temp_library):
        """Test that books can be deleted like regular items."""
        chapters = [
            {'title': 'Ch1', 'content': 'Content.', 'word_count': 1},
        ]

        book = library.create_book(
            title='Delete Me',
            filename='delete.md',
            chapters=chapters,
        )

        # Verify it exists
        assert library.get_item(book['id']) is not None

        # Delete it
        result = library.delete_item(book['id'])
        assert result == True

        # Verify it's gone
        assert library.get_item(book['id']) is None
        assert len(library.get_all_items()) == 0


class TestGetChapterText:
    """Tests for library.get_chapter_text()"""

    def test_get_chapter_text_valid_index(self, temp_library):
        """Test getting chapter text by valid index."""
        chapters = [
            {'title': 'Intro', 'content': 'Introduction content here.', 'word_count': 3},
            {'title': 'Chapter 1', 'content': '# Chapter 1\n\nMain content.', 'word_count': 4},
            {'title': 'Chapter 2', 'content': '# Chapter 2\n\nMore content.', 'word_count': 4},
        ]

        book = library.create_book(
            title='Chapter Book',
            filename='chapters.md',
            chapters=chapters,
        )

        # Get each chapter
        assert library.get_chapter_text(book['id'], 0) == 'Introduction content here.'
        assert library.get_chapter_text(book['id'], 1) == '# Chapter 1\n\nMain content.'
        assert library.get_chapter_text(book['id'], 2) == '# Chapter 2\n\nMore content.'

    def test_get_chapter_text_invalid_index(self, temp_library):
        """Test that invalid index returns None."""
        chapters = [
            {'title': 'Only Chapter', 'content': 'Content.', 'word_count': 1},
        ]

        book = library.create_book(
            title='One Chapter',
            filename='one.md',
            chapters=chapters,
        )

        assert library.get_chapter_text(book['id'], 1) is None
        assert library.get_chapter_text(book['id'], -1) is None
        assert library.get_chapter_text(book['id'], 100) is None

    def test_get_chapter_text_nonexistent_book(self, temp_library):
        """Test that nonexistent book returns None."""
        assert library.get_chapter_text('nonexistent-id', 0) is None

    def test_get_chapter_text_regular_item(self, temp_library):
        """Test that regular item (not book) returns None."""
        # Create a regular item
        item = library.create_item(
            markdown_content='# Regular Document\n\nJust a document.',
            filename='regular.md',
            title='Regular Doc',
        )

        # Should return None for regular items
        assert library.get_chapter_text(item['id'], 0) is None


class TestBookDuplicateDetection:
    """Tests for duplicate detection with books."""

    def test_book_hash_in_index(self, temp_library):
        """Test that book content hash can be found in index."""
        chapters = [
            {'title': 'Ch1', 'content': 'Unique content here.', 'word_count': 3},
        ]

        full_content = 'Unique content here.'
        content_hash = library.compute_content_hash(full_content)

        book = library.create_book(
            title='Hashable Book',
            filename='hash.md',
            chapters=chapters,
            content_hash=content_hash,
        )

        # Find by hash
        found = library.find_by_hash(content_hash)
        assert found is not None
        assert found['id'] == book['id']
        assert found['type'] == 'book'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
