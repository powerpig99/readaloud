"""
Tests for text_processor.py auto-chunking functions.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_processor import should_auto_chunk, split_into_chapters


class TestShouldAutoChunk:
    """Tests for should_auto_chunk function."""

    def test_short_text_returns_false(self):
        """Text under threshold should not be chunked."""
        text = "# Chapter 1\n\nShort content.\n\n## Section 1\n\nMore content."
        assert should_auto_chunk(text, word_threshold=5000) is False

    def test_long_text_without_headings_returns_false(self):
        """Long text without heading structure should not be chunked."""
        # Generate text with 6000 words but no headings
        text = "word " * 6000
        assert should_auto_chunk(text, word_threshold=5000) is False

    def test_long_text_with_one_heading_returns_false(self):
        """Long text with only one heading should not be chunked."""
        text = "# Only One Heading\n\n" + "word " * 6000
        assert should_auto_chunk(text, word_threshold=5000) is False

    def test_long_text_with_two_headings_returns_true(self):
        """Long text with two+ headings should be chunked."""
        text = "# Chapter 1\n\n" + "word " * 3000 + "\n\n# Chapter 2\n\n" + "word " * 3000
        assert should_auto_chunk(text, word_threshold=5000) is True

    def test_long_text_with_mixed_headings_returns_true(self):
        """Long text with # and ## headings should be chunked."""
        text = "# Chapter 1\n\n" + "word " * 3000 + "\n\n## Section 2\n\n" + "word " * 3000
        assert should_auto_chunk(text, word_threshold=5000) is True

    def test_deep_headings_not_counted(self):
        """### headings should not count toward the 2-heading minimum."""
        text = "### Deep Heading 1\n\n" + "word " * 3000 + "\n\n### Deep Heading 2\n\n" + "word " * 3000
        assert should_auto_chunk(text, word_threshold=5000) is False

    def test_custom_threshold(self):
        """Custom word threshold should be respected."""
        text = "# Chapter 1\n\n" + "word " * 100 + "\n\n# Chapter 2\n\nMore content."
        assert should_auto_chunk(text, word_threshold=50) is True
        assert should_auto_chunk(text, word_threshold=200) is False

    def test_cjk_text_word_count(self):
        """CJK characters should be counted as words."""
        # Each CJK character counts as one word
        text = "# 第一章\n\n" + "中" * 3000 + "\n\n# 第二章\n\n" + "文" * 3000
        assert should_auto_chunk(text, word_threshold=5000) is True


class TestSplitIntoChapters:
    """Tests for split_into_chapters function."""

    def test_simple_chapters(self):
        """Simple document with two chapters."""
        text = """# Chapter One

This is chapter one content.

# Chapter Two

This is chapter two content."""

        chapters = split_into_chapters(text)

        assert len(chapters) == 2
        assert chapters[0]['title'] == 'Chapter One'
        assert chapters[1]['title'] == 'Chapter Two'
        assert 'chapter one content' in chapters[0]['content'].lower()
        assert 'chapter two content' in chapters[1]['content'].lower()

    def test_intro_before_first_heading(self):
        """Content before first heading becomes Introduction chapter."""
        text = """This is introductory content before any heading.

# Chapter One

Chapter one content."""

        chapters = split_into_chapters(text)

        assert len(chapters) == 2
        assert chapters[0]['title'] == 'Introduction'
        assert 'introductory content' in chapters[0]['content'].lower()
        assert chapters[1]['title'] == 'Chapter One'

    def test_mixed_heading_levels(self):
        """Mix of # and ## headings should all create chapters."""
        text = """# Main Chapter

Main content.

## Sub Section

Sub section content.

# Another Chapter

More content."""

        chapters = split_into_chapters(text)

        assert len(chapters) == 3
        assert chapters[0]['title'] == 'Main Chapter'
        assert chapters[1]['title'] == 'Sub Section'
        assert chapters[2]['title'] == 'Another Chapter'

    def test_deep_headings_not_split(self):
        """### and deeper headings should not cause splits."""
        text = """# Chapter One

Some content.

### Deep Section

This deep section should stay in Chapter One.

#### Even Deeper

Still in Chapter One.

# Chapter Two

New chapter."""

        chapters = split_into_chapters(text)

        assert len(chapters) == 2
        assert chapters[0]['title'] == 'Chapter One'
        assert '### Deep Section' in chapters[0]['content']
        assert '#### Even Deeper' in chapters[0]['content']
        assert chapters[1]['title'] == 'Chapter Two'

    def test_word_count_included(self):
        """Each chapter should have accurate word count."""
        text = """# Short Chapter

One two three.

# Longer Chapter

One two three four five six seven eight nine ten."""

        chapters = split_into_chapters(text)

        assert chapters[0]['word_count'] > 0
        assert chapters[1]['word_count'] > chapters[0]['word_count']

    def test_cjk_chapters(self):
        """Chinese text should be properly split and counted."""
        text = """# 第一章

这是第一章的内容。

# 第二章

这是第二章的内容，比第一章长一些。"""

        chapters = split_into_chapters(text)

        assert len(chapters) == 2
        assert chapters[0]['title'] == '第一章'
        assert chapters[1]['title'] == '第二章'
        assert chapters[0]['word_count'] > 0
        assert chapters[1]['word_count'] > 0

    def test_empty_content_after_heading(self):
        """Heading with no content should still create a chapter."""
        text = """# Chapter One

Content here.

# Empty Chapter

# Chapter Three

More content."""

        chapters = split_into_chapters(text)

        assert len(chapters) == 3
        assert chapters[1]['title'] == 'Empty Chapter'
        # Empty chapter should have minimal word count (just the heading)
        assert chapters[1]['word_count'] >= 2  # "Empty Chapter"

    def test_heading_preserved_in_content(self):
        """The heading should be included in chapter content."""
        text = """# My Chapter Title

Chapter body text."""

        chapters = split_into_chapters(text)

        assert '# My Chapter Title' in chapters[0]['content']
        assert 'Chapter body text' in chapters[0]['content']

    def test_no_headings(self):
        """Text with no headings returns single Introduction chapter."""
        text = "Just some plain text without any headings at all."

        chapters = split_into_chapters(text)

        assert len(chapters) == 1
        assert chapters[0]['title'] == 'Introduction'
        assert chapters[0]['content'] == text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
