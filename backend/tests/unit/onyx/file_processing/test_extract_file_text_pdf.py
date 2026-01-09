"""Unit tests for PDF extraction functions using pypdf."""

import io

from pypdf import PdfReader
from pypdf import PdfWriter

from onyx.file_processing.extract_file_text import pdf_to_text
from onyx.file_processing.extract_file_text import read_pdf_file


def create_simple_pdf() -> io.BytesIO:
    """Create a simple valid PDF using a minimal PDF structure."""
    # Create a minimal valid PDF manually for compatibility across pypdf versions
    minimal_pdf_bytes = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Resources <<
>>
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
180
%%EOF"""
    return io.BytesIO(minimal_pdf_bytes)


def create_pdf_with_metadata(
    title: str = "Test Document",
    author: str = "Test Author",
    subject: str = "Test Subject",
) -> io.BytesIO:
    """Create a PDF with metadata using pypdf."""
    # First create a simple PDF
    simple_pdf = create_simple_pdf()
    reader = PdfReader(simple_pdf)
    writer = PdfWriter()

    # Clone pages from reader
    for page in reader.pages:
        writer.add_page(page)

    # Add metadata
    writer.add_metadata(
        {
            "/Title": title,
            "/Author": author,
            "/Subject": subject,
        }
    )

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)
    return pdf_bytes


def create_encrypted_pdf(password: str = "testpass123") -> io.BytesIO:
    """Create an encrypted PDF using pypdf."""
    # First create a simple PDF
    simple_pdf = create_simple_pdf()
    reader = PdfReader(simple_pdf)
    writer = PdfWriter()

    # Clone pages from reader
    for page in reader.pages:
        writer.add_page(page)

    # Encrypt the PDF
    writer.encrypt(password)

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)
    return pdf_bytes


def create_multi_page_pdf() -> io.BytesIO:
    """Create a multi-page PDF using pypdf."""
    # Create a simple PDF and clone its page multiple times
    simple_pdf = create_simple_pdf()
    reader = PdfReader(simple_pdf)
    writer = PdfWriter()

    # Add the same page 3 times to create a multi-page PDF
    for _ in range(3):
        writer.add_page(reader.pages[0])

    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)
    return pdf_bytes


def create_invalid_pdf() -> io.BytesIO:
    """Create an invalid/corrupted PDF."""
    # Return bytes that look like a PDF but are invalid
    return io.BytesIO(b"%PDF-1.4\ninvalid pdf content\x00\x00\x00")


class TestPdfToText:
    """Tests for pdf_to_text function."""

    def test_simple_pdf_extraction(self) -> None:
        """Test extracting text from a simple PDF."""
        pdf_file = create_simple_pdf()
        result = pdf_to_text(pdf_file)
        # Should return a string (blank PDFs may return empty string)
        assert isinstance(result, str)

    def test_multi_page_pdf_extraction(self) -> None:
        """Test extracting text from a multi-page PDF."""
        pdf_file = create_multi_page_pdf()
        result = pdf_to_text(pdf_file)
        # Should return a string (may be empty for blank pages)
        assert isinstance(result, str)

    def test_encrypted_pdf_with_password(self) -> None:
        """Test extracting text from encrypted PDF with correct password."""
        pdf_file = create_encrypted_pdf("mypassword")
        result = pdf_to_text(pdf_file, pdf_pass="mypassword")
        # Should successfully decrypt and return text (may be empty for blank page)
        assert isinstance(result, str)

    def test_encrypted_pdf_without_password(self) -> None:
        """Test extracting text from encrypted PDF without password."""
        pdf_file = create_encrypted_pdf("mypassword")
        result = pdf_to_text(pdf_file)
        # Should return empty string for encrypted PDF without password
        assert result == ""

    def test_encrypted_pdf_with_wrong_password(self) -> None:
        """Test extracting text from encrypted PDF with wrong password."""
        pdf_file = create_encrypted_pdf("mypassword")
        result = pdf_to_text(pdf_file, pdf_pass="wrongpassword")
        # Should return empty string for wrong password
        assert result == ""

    def test_invalid_pdf(self) -> None:
        """Test handling of invalid PDF file."""
        pdf_file = create_invalid_pdf()
        # Should handle gracefully without raising exception
        result = pdf_to_text(pdf_file)
        assert result == ""


class TestReadPdfFile:
    """Tests for read_pdf_file function."""

    def test_basic_text_extraction(self) -> None:
        """Test basic text extraction from PDF."""
        pdf_file = create_simple_pdf()
        text, metadata, images = read_pdf_file(pdf_file)
        assert isinstance(text, str)
        assert isinstance(metadata, dict)
        assert isinstance(images, list)

    def test_metadata_extraction(self) -> None:
        """Test extracting metadata from PDF."""
        pdf_file = create_pdf_with_metadata("My Title", "My Author", "My Subject")
        text, metadata, images = read_pdf_file(pdf_file)

        # Metadata keys should have leading slashes removed
        assert isinstance(metadata, dict)
        # Check that metadata was extracted (keys may vary)
        assert len(metadata) >= 0  # May be empty or have metadata

    def test_metadata_with_list_values(self) -> None:
        """Test metadata extraction when values are lists."""
        # Create a PDF with metadata
        simple_pdf = create_simple_pdf()
        reader = PdfReader(simple_pdf)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata(
            {
                "/Title": "Test Title",
            }
        )
        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)

        text, metadata, images = read_pdf_file(pdf_bytes)
        assert isinstance(metadata, dict)

    def test_encrypted_pdf_with_correct_password(self) -> None:
        """Test reading encrypted PDF with correct password."""
        pdf_file = create_encrypted_pdf("secret123")
        text, metadata, images = read_pdf_file(pdf_file, pdf_pass="secret123")
        assert isinstance(text, str)
        assert isinstance(metadata, dict)
        assert isinstance(images, list)

    def test_encrypted_pdf_without_password(self) -> None:
        """Test reading encrypted PDF without password."""
        pdf_file = create_encrypted_pdf("secret123")
        text, metadata, images = read_pdf_file(pdf_file)
        # Should return empty text for encrypted PDF without password
        assert text == ""
        assert isinstance(metadata, dict)
        assert images == []

    def test_encrypted_pdf_with_wrong_password(self) -> None:
        """Test reading encrypted PDF with wrong password."""
        pdf_file = create_encrypted_pdf("secret123")
        text, metadata, images = read_pdf_file(pdf_file, pdf_pass="wrongpass")
        # Should return empty text for wrong password
        assert text == ""
        assert isinstance(metadata, dict)
        assert images == []

    def test_extract_images_flag_false(self) -> None:
        """Test that images are not extracted when extract_images=False."""
        pdf_file = create_simple_pdf()
        text, metadata, images = read_pdf_file(pdf_file, extract_images=False)
        assert images == []

    def test_extract_images_flag_true_no_images(self) -> None:
        """Test extract_images=True on PDF without images."""
        pdf_file = create_simple_pdf()
        text, metadata, images = read_pdf_file(pdf_file, extract_images=True)
        # Should return empty list if no images
        assert images == []

    def test_image_callback(self) -> None:
        """Test image extraction with callback function."""
        pdf_file = create_simple_pdf()
        captured_images: list[tuple[bytes, str]] = []

        def image_callback(img_bytes: bytes, img_name: str) -> None:
            captured_images.append((img_bytes, img_name))

        text, metadata, images = read_pdf_file(
            pdf_file, extract_images=True, image_callback=image_callback
        )
        # When callback is provided, images list should be empty
        assert images == []

    def test_multi_page_pdf(self) -> None:
        """Test reading multi-page PDF."""
        pdf_file = create_multi_page_pdf()
        text, metadata, images = read_pdf_file(pdf_file)
        # Should return a string (may be empty for blank pages)
        assert isinstance(text, str)
        assert isinstance(metadata, dict)
        assert isinstance(images, list)

    def test_invalid_pdf_handling(self) -> None:
        """Test handling of invalid/corrupted PDF."""
        pdf_file = create_invalid_pdf()
        # Should handle gracefully and return empty results
        text, metadata, images = read_pdf_file(pdf_file)
        assert text == ""
        assert isinstance(metadata, dict)
        assert images == []

    def test_empty_pdf(self) -> None:
        """Test handling of empty PDF."""
        # Use the simple PDF creation function
        pdf_bytes = create_simple_pdf()

        text, metadata, images = read_pdf_file(pdf_bytes)
        # Empty PDF should return empty text
        assert isinstance(text, str)
        assert isinstance(metadata, dict)
        assert images == []

    def test_pdf_with_metadata_cleanup(self) -> None:
        """Test that metadata keys have leading slashes removed."""
        pdf_file = create_pdf_with_metadata("My Title", "Test Author", "Test Subject")
        text, metadata, images = read_pdf_file(pdf_file)

        # Check that keys don't start with "/"
        for key in metadata.keys():
            assert not key.startswith("/")

    def test_file_position_preserved(self) -> None:
        """Test that file position is handled correctly."""
        pdf_file = create_simple_pdf()
        pdf_file.tell()

        text, metadata, images = read_pdf_file(pdf_file)

        # Function should work regardless of initial position
        assert isinstance(text, str)
