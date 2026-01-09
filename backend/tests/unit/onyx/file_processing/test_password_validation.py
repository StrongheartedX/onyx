"""Unit tests for password validation functions using pypdf."""

import io

from pypdf import PdfWriter

from onyx.file_processing.password_validation import is_file_password_protected
from onyx.file_processing.password_validation import is_pdf_protected


def create_simple_pdf() -> io.BytesIO:
    """Create a simple unencrypted PDF."""
    # Create a minimal valid PDF manually for compatibility
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


def create_encrypted_pdf(password: str = "testpass123") -> io.BytesIO:
    """Create an encrypted PDF."""
    # First create a simple PDF
    simple_pdf = create_simple_pdf()
    from pypdf import PdfReader

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


class TestIsPdfProtected:
    """Tests for is_pdf_protected function."""

    def test_unencrypted_pdf(self) -> None:
        """Test that unencrypted PDF returns False."""
        pdf_file = create_simple_pdf()
        assert is_pdf_protected(pdf_file) is False

    def test_encrypted_pdf(self) -> None:
        """Test that encrypted PDF returns True."""
        pdf_file = create_encrypted_pdf("mypassword")
        assert is_pdf_protected(pdf_file) is True

    def test_file_position_preserved(self) -> None:
        """Test that file position is preserved after check."""
        pdf_file = create_simple_pdf()
        pdf_file.tell()

        # Move file pointer
        pdf_file.seek(10)
        pos_before_call = pdf_file.tell()

        result = is_pdf_protected(pdf_file)

        # Position should be restored to position before function call
        assert pdf_file.tell() == pos_before_call
        assert result is False

    def test_multiple_calls_same_file(self) -> None:
        """Test that function can be called multiple times on same file."""
        pdf_file = create_simple_pdf()

        result1 = is_pdf_protected(pdf_file)
        result2 = is_pdf_protected(pdf_file)

        assert result1 == result2
        assert result1 is False

    def test_encrypted_pdf_different_passwords(self) -> None:
        """Test that encrypted PDF is detected regardless of password."""
        pdf_file = create_encrypted_pdf("password1")
        assert is_pdf_protected(pdf_file) is True

        # Create another encrypted PDF with different password
        pdf_file2 = create_encrypted_pdf("password2")
        assert is_pdf_protected(pdf_file2) is True


class TestIsFilePasswordProtected:
    """Tests for is_file_password_protected function."""

    def test_pdf_unencrypted(self) -> None:
        """Test unencrypted PDF file."""
        pdf_file = create_simple_pdf()
        assert is_file_password_protected(pdf_file, "test.pdf") is False

    def test_pdf_encrypted(self) -> None:
        """Test encrypted PDF file."""
        pdf_file = create_encrypted_pdf("mypassword")
        assert is_file_password_protected(pdf_file, "test.pdf") is True

    def test_pdf_with_explicit_extension(self) -> None:
        """Test PDF with explicit extension parameter."""
        pdf_file = create_encrypted_pdf("pass")
        assert (
            is_file_password_protected(pdf_file, "document", extension=".pdf") is True
        )

    def test_non_pdf_file(self) -> None:
        """Test that non-PDF files return False."""
        text_file = io.BytesIO(b"Not a PDF file")
        assert is_file_password_protected(text_file, "test.txt") is False

    def test_unsupported_extension(self) -> None:
        """Test file with unsupported extension."""
        text_file = io.BytesIO(b"Some content")
        assert is_file_password_protected(text_file, "test.xyz") is False

    def test_pdf_case_insensitive_extension(self) -> None:
        """Test that PDF extension is case-insensitive."""
        pdf_file = create_encrypted_pdf("pass")
        assert is_file_password_protected(pdf_file, "test.PDF") is True
        assert is_file_password_protected(pdf_file, "test.Pdf") is True

    def test_file_position_preserved(self) -> None:
        """Test that file position is preserved."""
        pdf_file = create_simple_pdf()
        pdf_file.tell()

        pdf_file.seek(5)
        pos_before_call = pdf_file.tell()
        result = is_file_password_protected(pdf_file, "test.pdf")

        # Position should be restored to position before function call
        assert pdf_file.tell() == pos_before_call
        assert result is False
