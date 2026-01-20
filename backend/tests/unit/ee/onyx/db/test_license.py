"""Tests for license database CRUD operations."""

from unittest.mock import MagicMock
from unittest.mock import patch

from ee.onyx.db.license import check_seat_availability
from ee.onyx.db.license import delete_license
from ee.onyx.db.license import get_license
from ee.onyx.db.license import get_used_seats
from ee.onyx.db.license import upsert_license
from onyx.db.models import License


class TestGetLicense:
    """Tests for get_license function."""

    def test_get_existing_license(self) -> None:
        """Test getting an existing license."""
        mock_session = MagicMock()
        mock_license = License(id=1, license_data="test_data")

        # Mock the query chain
        mock_session.execute.return_value.scalars.return_value.first.return_value = (
            mock_license
        )

        result = get_license(mock_session)

        assert result is not None
        assert result.license_data == "test_data"
        mock_session.execute.assert_called_once()

    def test_get_no_license(self) -> None:
        """Test getting when no license exists."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.first.return_value = None

        result = get_license(mock_session)

        assert result is None


class TestUpsertLicense:
    """Tests for upsert_license function."""

    def test_insert_new_license(self) -> None:
        """Test inserting a new license when none exists."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.first.return_value = None

        upsert_license(mock_session, "new_license_data")

        # Verify add was called with a License object
        mock_session.add.assert_called_once()
        added_license = mock_session.add.call_args[0][0]
        assert isinstance(added_license, License)
        assert added_license.license_data == "new_license_data"

        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_update_existing_license(self) -> None:
        """Test updating an existing license."""
        mock_session = MagicMock()
        existing_license = License(id=1, license_data="old_data")
        mock_session.execute.return_value.scalars.return_value.first.return_value = (
            existing_license
        )

        upsert_license(mock_session, "updated_license_data")

        # Verify the existing license was updated
        assert existing_license.license_data == "updated_license_data"
        mock_session.add.assert_not_called()  # Should not add new
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(existing_license)


class TestDeleteLicense:
    """Tests for delete_license function."""

    def test_delete_existing_license(self) -> None:
        """Test deleting an existing license."""
        mock_session = MagicMock()
        existing_license = License(id=1, license_data="test_data")
        mock_session.execute.return_value.scalars.return_value.first.return_value = (
            existing_license
        )

        result = delete_license(mock_session)

        assert result is True
        mock_session.delete.assert_called_once_with(existing_license)
        mock_session.commit.assert_called_once()

    def test_delete_no_license(self) -> None:
        """Test deleting when no license exists."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalars.return_value.first.return_value = None

        result = delete_license(mock_session)

        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()


class TestGetUsedSeats:
    """Tests for get_used_seats function."""

    @patch("ee.onyx.db.license.MULTI_TENANT", True)
    @patch("ee.onyx.db.license.get_current_tenant_id")
    @patch("ee.onyx.server.tenants.user_mapping.get_tenant_count")
    def test_multi_tenant_uses_tenant_count(
        self,
        mock_get_tenant_count: MagicMock,
        mock_get_tenant_id: MagicMock,
    ) -> None:
        """Multi-tenant mode should use get_tenant_count."""
        mock_get_tenant_id.return_value = "test_tenant"
        mock_get_tenant_count.return_value = 5

        result = get_used_seats()

        assert result == 5
        mock_get_tenant_count.assert_called_once_with("test_tenant")

    @patch("ee.onyx.db.license.MULTI_TENANT", True)
    @patch("ee.onyx.server.tenants.user_mapping.get_tenant_count")
    def test_multi_tenant_with_explicit_tenant_id(
        self,
        mock_get_tenant_count: MagicMock,
    ) -> None:
        """Explicit tenant_id should be used when provided."""
        mock_get_tenant_count.return_value = 10

        result = get_used_seats(tenant_id="explicit_tenant")

        assert result == 10
        mock_get_tenant_count.assert_called_once_with("explicit_tenant")

    @patch("ee.onyx.db.license.MULTI_TENANT", False)
    @patch("onyx.db.engine.sql_engine.get_session_with_current_tenant")
    def test_self_hosted_counts_active_users(
        self,
        mock_get_session: MagicMock,
    ) -> None:
        """Self-hosted mode should count active users from User table."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.scalar.return_value = 15
        mock_get_session.return_value = mock_session

        result = get_used_seats()

        assert result == 15


class TestCheckSeatAvailability:
    """Tests for check_seat_availability function."""

    @patch("ee.onyx.db.license.get_cached_license_metadata")
    def test_no_license_returns_unlimited(
        self,
        mock_get_metadata: MagicMock,
    ) -> None:
        """No license means unlimited seats (no enforcement)."""
        mock_get_metadata.return_value = None

        available, error = check_seat_availability()

        assert available is True
        assert error is None

    @patch("ee.onyx.db.license.get_used_seats")
    @patch("ee.onyx.db.license.get_cached_license_metadata")
    def test_seats_available(
        self,
        mock_get_metadata: MagicMock,
        mock_get_used_seats: MagicMock,
    ) -> None:
        """When seats are available, return True."""
        mock_metadata = MagicMock()
        mock_metadata.seats = 10
        mock_get_metadata.return_value = mock_metadata
        mock_get_used_seats.return_value = 5  # 5 used, 5 available

        available, error = check_seat_availability(seats_needed=3)

        assert available is True
        assert error is None

    @patch("ee.onyx.db.license.get_used_seats")
    @patch("ee.onyx.db.license.get_cached_license_metadata")
    def test_seats_at_limit(
        self,
        mock_get_metadata: MagicMock,
        mock_get_used_seats: MagicMock,
    ) -> None:
        """When at seat limit, return False with error message."""
        mock_metadata = MagicMock()
        mock_metadata.seats = 10
        mock_get_metadata.return_value = mock_metadata
        mock_get_used_seats.return_value = 10  # All seats used

        available, error = check_seat_availability(seats_needed=1)

        assert available is False
        assert error is not None
        assert "Seat limit reached" in error
        assert "10/10" in error

    @patch("ee.onyx.db.license.get_used_seats")
    @patch("ee.onyx.db.license.get_cached_license_metadata")
    def test_requesting_more_than_available(
        self,
        mock_get_metadata: MagicMock,
        mock_get_used_seats: MagicMock,
    ) -> None:
        """When requesting more seats than available, return False."""
        mock_metadata = MagicMock()
        mock_metadata.seats = 10
        mock_get_metadata.return_value = mock_metadata
        mock_get_used_seats.return_value = 8  # 2 available

        available, error = check_seat_availability(seats_needed=5)

        assert available is False
        assert error is not None
        assert "Seat limit reached" in error

    @patch("ee.onyx.db.license.get_used_seats")
    @patch("ee.onyx.db.license.get_cached_license_metadata")
    def test_exact_seats_available(
        self,
        mock_get_metadata: MagicMock,
        mock_get_used_seats: MagicMock,
    ) -> None:
        """When exactly enough seats are available, return True."""
        mock_metadata = MagicMock()
        mock_metadata.seats = 10
        mock_get_metadata.return_value = mock_metadata
        mock_get_used_seats.return_value = 7  # 3 available

        available, error = check_seat_availability(seats_needed=3)

        assert available is True
        assert error is None
