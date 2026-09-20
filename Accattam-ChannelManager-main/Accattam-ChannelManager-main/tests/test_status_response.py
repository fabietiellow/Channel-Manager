"""Unit test module for verifying the application's root endpoint."""


class TestStatusResponse:
    """Test suite for checking the application's HTTP status responses."""

    def test_index_response(self, client):
        """Test that the index route responds correctly.

        Args:
            client (FlaskClient): The test client fixture provided by pytest.

        Asserts:
            The HTTP response status code is 200 (OK).
        """

        response = client.get("/")
        assert response.status_code == 200
