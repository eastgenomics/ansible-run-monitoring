import unittest
import os
import sys

sys.path.append(".")
from bin.jira import Jira

# import relevant envs
TOKEN = os.environ["JIRA_TOKEN"]
EMAIL = os.environ["JIRA_EMAIL"]
URL = os.environ["JIRA_API_URL"]

ONE_SAMPLE = "220304_A01295_0063_AH7TFVDMXY"
MULTIPLE_SAMPLE = "ansible"


class TestJira(unittest.TestCase):
    def test_jira_search_issue_function(self) -> None:
        jira = Jira(TOKEN, EMAIL, URL, True)
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
                len(data["issues"]),
                1,
                "search_issue not returning result for proper Jira issue",
            )
            self.assertGreater(
                len(datab["issues"]),
                1,
                "return 1 or no ticket for multiple-return ticket",
            )

    def test_jira_get_issue_detail_function(self) -> None:
        jira = Jira(TOKEN, EMAIL, URL, False)
        # Test run with 1 known ticket
        assay, status, key = jira.get_issue_detail(ONE_SAMPLE)
        self.assertEqual(
            [assay, status.upper(), key],
            ["TWE", "ALL SAMPLES RELEASED", "EBH-922"],
            "search_issue return faulty for single ticket",
        )

        # Exclude ticket with RequestType != SequencingType
        assay, status, key = jira.get_issue_detail("230223_A01295_0161_BHVH73DRX2")
        self.assertEqual(
            [assay, status, key],
            ["CEN", "All samples released", "EBH-1568"],
            "search_issue return faulty for multiple-ticket issue",
        )

if __name__ == "__main__":
    unittest.main()
