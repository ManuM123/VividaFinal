import os

from playwright.sync_api import Page, expect


BASE_URL = os.getenv("VIVIDA_E2E_BASE_URL", "http://127.0.0.1:3000")


def test_sign_in_page_loads(page: Page):
    page.goto(BASE_URL)

    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
    expect(page.get_by_text("Welcome to Vivida")).to_be_visible()
    expect(page.get_by_label("Email")).to_be_visible()


def test_magic_link_validation_message(page: Page):
    page.goto(BASE_URL)
    page.get_by_label("Email").fill("test@example.com")
    page.get_by_role("button", name="Send sign-in link").click()

    expect(page.get_by_text("Check your email")).to_be_visible(timeout=10000)


def test_manifest_is_available(page: Page):
    response = page.goto(f"{BASE_URL}/manifest.webmanifest")

    assert response is not None
    assert response.ok
    assert "Vivida" in page.content()
