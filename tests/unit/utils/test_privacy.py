"""Tests for the PII redaction filter (utils/privacy.py)."""

from mcp_atlassian.utils.privacy import _iban_valid, _luhn_valid, redact


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


class TestNoOpCases:
    def test_empty_string(self):
        assert redact("") == ""

    def test_non_string_passthrough(self):
        assert redact(None) is None  # type: ignore[arg-type]

    def test_plain_text_unchanged(self):
        assert redact("No sensitive data here.") == "No sensitive data here."

    def test_enabled_by_default(self):
        # Must redact even without setting the env var
        assert "[REDACTED_EMAIL]" in redact("contact user@example.com")

    def test_opt_out_via_env_var(self, monkeypatch):
        monkeypatch.setenv("PRIVACY_FILTER_ENABLED", "false")
        text = "contact user@example.com"
        assert redact(text) == text

    def test_opt_out_values(self, monkeypatch):
        for value in ("false", "0", "no", "False", "NO"):
            monkeypatch.setenv("PRIVACY_FILTER_ENABLED", value)
            text = "contact user@example.com"
            assert redact(text) == text, f"Expected no redaction for PRIVACY_FILTER_ENABLED={value}"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


class TestEmailRedaction:
    def test_simple_email(self):
        assert redact("Send to alice@example.com please") == "Send to [REDACTED_EMAIL] please"

    def test_email_with_subdomain(self):
        result = redact("user@mail.corp.example.org")
        assert "[REDACTED_EMAIL]" in result

    def test_multiple_emails(self):
        result = redact("From a@x.com to b@y.com")
        assert result.count("[REDACTED_EMAIL]") == 2


# ---------------------------------------------------------------------------
# IPv4
# ---------------------------------------------------------------------------


class TestIPv4Redaction:
    def test_ipv4(self):
        assert "[REDACTED_IP]" in redact("Server at 192.168.1.100")

    def test_ipv4_in_url_context(self):
        assert "[REDACTED_IP]" in redact("Connect to 10.0.0.1 on port 443")


# ---------------------------------------------------------------------------
# IPv6
# ---------------------------------------------------------------------------


class TestIPv6Redaction:
    def test_full_ipv6(self):
        assert "[REDACTED_IPV6]" in redact("Address: 2001:0db8:85a3:0000:0000:8a2e:0370:7334")

    def test_compressed_ipv6(self):
        assert "[REDACTED_IPV6]" in redact("Loopback ::1 is special")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


class TestJWTRedaction:
    def test_jwt_token(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        assert "[REDACTED_JWT]" in redact(f"Authorization: Bearer {token}")

    def test_jwt_not_confused_with_email(self):
        result = redact("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1In0.abc user@example.com")
        assert "[REDACTED_JWT]" in result
        assert "[REDACTED_EMAIL]" in result


# ---------------------------------------------------------------------------
# Credit card
# ---------------------------------------------------------------------------


class TestLuhnValidator:
    def test_valid_luhn(self):
        assert _luhn_valid("4111111111111111") is True

    def test_invalid_luhn(self):
        assert _luhn_valid("1234567890123456") is False


class TestCreditCardRedaction:
    def test_cc_with_spaces(self):
        assert "[REDACTED_CC]" in redact("Card: 4111 1111 1111 1111")

    def test_cc_with_dashes(self):
        assert "[REDACTED_CC]" in redact("Card: 4111-1111-1111-1111")

    def test_cc_no_separator(self):
        assert "[REDACTED_CC]" in redact("Card number is 4111111111111111")

    def test_non_luhn_digit_sequence_not_redacted(self):
        # 16-digit Confluence page ID that fails Luhn — must not be redacted
        assert "[REDACTED_CC]" not in redact("pageId=1234567890123456")


# ---------------------------------------------------------------------------
# IBAN
# ---------------------------------------------------------------------------


class TestIBANValidator:
    def test_valid_german_iban(self):
        assert _iban_valid("DE89370400440532013000") is True

    def test_invalid_iban(self):
        assert _iban_valid("DE00370400440532013000") is False


class TestIBANRedaction:
    def test_german_iban(self):
        assert "[REDACTED_IBAN]" in redact("IBAN: DE89370400440532013000")

    def test_gb_iban(self):
        assert "[REDACTED_IBAN]" in redact("Account GB29NWBK60161331926819")

    def test_jira_issue_key_not_redacted(self):
        # Jira keys like PROJ-123 don't match the pattern, but ensure
        # uppercase two-letter prefixed strings with bad MOD-97 are not redacted
        assert "[REDACTED_IBAN]" not in redact("Project: AB00INVALIDIBAN1234")


# ---------------------------------------------------------------------------
# Inline key=value secrets
# ---------------------------------------------------------------------------


class TestKeyValueSecretRedaction:
    def test_password_equals(self):
        result = redact("password=supersecret123")
        assert "[REDACTED]" in result
        assert "supersecret123" not in result

    def test_passwd_variant(self):
        result = redact("passwd=supersecret123")
        assert "[REDACTED]" in result
        assert "supersecret123" not in result

    def test_pwd_variant(self):
        result = redact("pwd=supersecret123")
        assert "[REDACTED]" in result
        assert "supersecret123" not in result

    def test_passphrase_variant(self):
        result = redact("passphrase=mysecretphrase")
        assert "[REDACTED]" in result
        assert "mysecretphrase" not in result

    def test_secret_variant(self):
        result = redact("secret=topsecretvalue")
        assert "[REDACTED]" in result
        assert "topsecretvalue" not in result

    def test_token_colon(self):
        result = redact("token: abcXYZ9876")
        assert "[REDACTED]" in result
        assert "abcXYZ9876" not in result

    def test_api_key(self):
        result = redact("api_key=my-api-key-value")
        assert "[REDACTED]" in result

    def test_api_key_camel(self):
        result = redact("apiKey=my-api-key-value")
        assert "[REDACTED]" in result

    def test_private_key(self):
        result = redact("private_key=-----BEGIN RSA")
        assert "[REDACTED]" in result

    def test_client_secret(self):
        result = redact("client_secret=abc123xyz789")
        assert "[REDACTED]" in result
        assert "abc123xyz789" not in result

    def test_access_token(self):
        result = redact("access_token=glpat-xxxxxxxxxxxx")
        assert "[REDACTED]" in result
        assert "glpat-xxxxxxxxxxxx" not in result

    def test_refresh_token(self):
        result = redact("refresh_token=v1.refresh.abc123")
        assert "[REDACTED]" in result
        assert "v1.refresh.abc123" not in result

    def test_bearer_in_curl(self):
        result = redact('curl -H "authorization: Bearer sometoken123"')
        assert "[REDACTED]" in result
        assert "sometoken123" not in result

    def test_key_name_preserved(self):
        result = redact("password=hunter2")
        assert result.startswith("password")


# ---------------------------------------------------------------------------
# Integration: Jira issue model (summary + ADF description)
# ---------------------------------------------------------------------------


class TestJiraIssueModelRedaction:
    def test_summary_is_redacted(self):
        from mcp_atlassian.models.jira.issue import JiraIssue

        data = {
            "id": "1",
            "key": "PROJ-1",
            "fields": {"summary": "Login failure for user@example.com"},
        }
        issue = JiraIssue.from_api_response(data)
        assert "[REDACTED_EMAIL]" in issue.summary
        assert "user@example.com" not in issue.summary

    def test_adf_custom_field_is_redacted(self):
        from mcp_atlassian.models.jira.issue import JiraIssue

        adf_body = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Akzeptiert wenn user@corp.com bestätigt.",
                        }
                    ],
                }
            ],
        }
        data = {
            "id": "1",
            "key": "NOP-1",
            "fields": {
                "summary": "Test",
                "customfield_11001": adf_body,
            },
        }
        issue = JiraIssue.from_api_response(
            data, requested_fields=["customfield_11001"]
        )
        simplified = issue.to_simplified_dict()
        value = simplified["customfield_11001"]["value"]
        assert "[REDACTED_EMAIL]" in value
        assert "user@corp.com" not in value

    def test_adf_description_is_redacted(self):
        from mcp_atlassian.models.jira.issue import JiraIssue

        data = {
            "id": "1",
            "key": "PROJ-1",
            "fields": {
                "summary": "Test issue",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Contact admin@corp.com for details.",
                                }
                            ],
                        }
                    ],
                },
            },
        }
        issue = JiraIssue.from_api_response(data)
        assert "[REDACTED_EMAIL]" in issue.description
        assert "admin@corp.com" not in issue.description


# ---------------------------------------------------------------------------
# Integration: Confluence page model (title)
# ---------------------------------------------------------------------------


class TestConfluencePageModelRedaction:
    def test_title_is_redacted(self):
        from mcp_atlassian.models.confluence.page import ConfluencePage

        data = {
            "id": "123",
            "title": "Notes for user@example.com",
            "type": "page",
            "status": "current",
        }
        page = ConfluencePage.from_api_response(data)
        assert "[REDACTED_EMAIL]" in page.title
        assert "user@example.com" not in page.title


# ---------------------------------------------------------------------------
# Integration: Jira changelog model
# ---------------------------------------------------------------------------


class TestJiraChangelogRedaction:
    def test_changelog_to_string_is_redacted(self):
        from mcp_atlassian.models.jira.common import JiraChangelogItem

        data = {
            "field": "description",
            "fieldtype": "jira",
            "fromString": "Old text with user@example.com",
            "toString": "New text with 192.168.0.1",
        }
        item = JiraChangelogItem.from_api_response(data)
        assert "[REDACTED_EMAIL]" in item.from_string
        assert "user@example.com" not in item.from_string
        assert "[REDACTED_IP]" in item.to_string
        assert "192.168.0.1" not in item.to_string

    def test_changelog_none_values_unchanged(self):
        from mcp_atlassian.models.jira.common import JiraChangelogItem

        data = {"field": "status", "fieldtype": "jira"}
        item = JiraChangelogItem.from_api_response(data)
        assert item.from_string is None
        assert item.to_string is None


# ---------------------------------------------------------------------------
# Integration: Confluence page ancestors
# ---------------------------------------------------------------------------


class TestConfluenceAncestorRedaction:
    def test_ancestor_title_is_redacted(self):
        from mcp_atlassian.models.confluence.page import ConfluencePage

        data = {
            "id": "42",
            "title": "Child Page",
            "type": "page",
            "status": "current",
            "ancestors": [
                {"id": "1", "title": "Notes for admin@corp.com"},
            ],
        }
        page = ConfluencePage.from_api_response(data)
        simplified = page.to_simplified_dict()
        ancestor_title = simplified["ancestors"][0]["title"]
        assert "[REDACTED_EMAIL]" in ancestor_title
        assert "admin@corp.com" not in ancestor_title


# ---------------------------------------------------------------------------
# Integration: combined text
# ---------------------------------------------------------------------------


class TestCombinedText:
    def test_ticket_description(self):
        description = (
            "User john.doe@company.com reported login failure from 203.0.113.42.\n"
            "Their API key is api_key=sk-abcdef1234567890 and card 4111 1111 1111 1111."
        )
        result = redact(description)
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_IP]" in result
        assert "[REDACTED]" in result
        assert "[REDACTED_CC]" in result
        assert "john.doe@company.com" not in result
        assert "203.0.113.42" not in result
        assert "sk-abcdef1234567890" not in result
        assert "4111 1111 1111 1111" not in result
