"""Existing smoke tests for auth flow — used as reference by RAG."""

import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:3000"


@pytest.fixture
def auth_page(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    return page


class TestLoginSmoke:
    """Basic smoke tests for the login page."""

    def test_login_page_loads(self, auth_page: Page):
        """Verify the login page renders correctly."""
        expect(auth_page.locator("[data-testid='login-title']")).to_have_text("Sign In")
        expect(auth_page.locator("[data-testid='email-input']")).to_be_visible()
        expect(auth_page.locator("[data-testid='password-input']")).to_be_visible()
        expect(auth_page.locator("[data-testid='login-submit-btn']")).to_be_enabled()

    def test_login_with_valid_credentials(self, auth_page: Page):
        """Verify successful login redirects to dashboard."""
        auth_page.locator("[data-testid='email-input']").fill("user@example.com")
        auth_page.locator("[data-testid='password-input']").fill("ValidPass123!")
        auth_page.locator("[data-testid='login-submit-btn']").click()
        auth_page.wait_for_url("**/dashboard**")
        expect(auth_page).to_have_url(f"{BASE_URL}/dashboard")

    def test_login_with_wrong_password(self, auth_page: Page):
        """Verify error banner on invalid credentials."""
        auth_page.locator("[data-testid='email-input']").fill("user@example.com")
        auth_page.locator("[data-testid='password-input']").fill("WrongPass!")
        auth_page.locator("[data-testid='login-submit-btn']").click()
        error = auth_page.locator("[data-testid='login-error-banner']")
        expect(error).to_be_visible()
