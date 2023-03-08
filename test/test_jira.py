import unittest
import os

from bin.jira import Jira

# import relevant envs
TOKEN = os.environ["JIRA_TOKEN"]
EMAIL = os.environ["JIRA_EMAIL"]
URL = os.environ["JIRA_API_URL"]
SERVER_TESTING = os.environ.get("ANSIBLE_TESTING", False)

ONE_SAMPLE = "220304_A01295_0063_AH7TFVDMXY"
MULTIPLE_SAMPLE = "ansible"

jira = Jira(TOKEN, EMAIL, URL, True)


class TestJira(unittest.TestCase):
    def test_jira_search_issue_function(self) -> None:
        data = jira.search_issue(ONE_SAMPLE, "EBHD")
        datab = jira.search_issue(MULTIPLE_SAMPLE, "EBHD")

        with self.subTest():
            self.assertTrue(
                isinstance(data, dict),
                "search_issue not returning result for proper Jira issue",
            )
            self.assertTrue(
                isinstance(data["issues"], list),
                "search_issue not returning result for proper Jira issue",
            )
            self.assertEqual(
                data["total"],
                1,
                "search_issue not returning result for proper Jira issue",
            )
            self.assertGreater(
                len(datab["issues"]),
                1,
                "return 1 or no ticket for multiple-return ticket",
            )

    def test_jira_get_issue_detail_function(self) -> None:
        assay, status, key = jira.get_issue_detail(ONE_SAMPLE, SERVER_TESTING)

        assay_b, status_b, key_b = jira.get_issue_detail(
            MULTIPLE_SAMPLE, SERVER_TESTING
        )

        # NEW TEST: Exclude ticket with RequestType != SequencingType
        assay_c, status_c, key_c = jira.get_issue_detail(
            "230223_A01295_0161_BHVH73DRX2", True
        )

        self.assertEqual(
            [assay, status.upper(), key],
            ["MYE", "NEW", "EBHD-587"],
            "search_issue return faulty for single ticket",
        )

        self.assertEqual(
            [assay_b, status_b, key_b],
            [
                "More than 1 Jira ticket detected",
                "More than 1 Jira ticket detected",
                None,
            ],
            "search_issue return faulty for multiple-ticket issue",
        )

        self.assertEqual(
            [assay_c, status_c, key_c],
            ["CEN", "All samples released", "EBH-1568"],
            "search_issue return faulty for multiple-ticket issue",
        )


if __name__ == "__main__":
    unittest.main()
