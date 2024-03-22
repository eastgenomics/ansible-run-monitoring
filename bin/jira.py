import json
from time import sleep
from typing import Union

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util import Retry


class Assignee(object):
    """
    Assignee object for Jira assignee
    """

    def __init__(self, data):
        self.id = data.get("accountId", None)
        self.active = data.get("active", None)
        self.name = data.get("displayName", None)
        self.timezone = data.get("timeZone", None)


class Reporter(object):
    """
    Reporter object for Jira reporter
    """

    def __init__(self, data):
        self.id = data.get("accountId", None)
        self.account_type = data.get("accountType", None)
        self.active = data.get("active", None)
        self.name = data.get("displayName", None)
        self.email = data.get("emailAddress", None)
        self.time = data.get("timeZone", None)


class Creator(object):
    """
    Creator object for Jira creator
    """

    def __init__(self, data):
        self.id = data.get("accountId", None)
        self.account_type = data.get("accountType", None)
        self.active = data.get("active", None)
        self.name = data.get("displayName", None)
        self.time = data.get("timeZone", None)


class Priority(object):
    """
    Priority object for priority in Jira ticket
    """

    def __init__(self, data):
        self.id = data.get("id", None)
        self.name = data.get("name", None)


class Project(object):
    """
    Project object for project in Jira ticket
    """

    def __init__(self, data):
        self.id = data.get("id", None)
        self.key = data.get("key", None)
        self.name = data.get("name", None)
        self.category = data.get("projectCategory", None)


class Status(object):
    """
    Status object for status in Jira ticket
    """

    def __init__(self, data):
        self.id = data.get("id", None)
        self.name = data.get("name", None)
        self.category = data.get("statusCategory", None)


class Issue(object):
    """
    Issue object for Jira issue
    """

    def __init__(self, data):
        self.id = data["id"]
        self.key = data["key"]

        fields = data["fields"]
        self.created = fields.get("created", None)
        self.creator = Creator(fields.get("creator", {})).__dict__
        self.priority = Priority(fields.get("priority", {})).__dict__
        self.summary = fields.get("summary", None)
        self.updated = fields.get("updated", None)
        if "assignee" in fields:
            if fields["assignee"] is not None:
                self.assignee = Assignee(fields.get("assignee", {})).__dict__
            else:
                self.assignee = None
        else:
            self.assignee = None
        if "status" in fields:
            self.status = Status(fields.get("status", {}))
        else:
            self.status = None
        if "project" in fields:
            self.project = Project(fields.get("project", {})).__dict__
        else:
            self.project = None
        if "reporter" in fields:
            self.reporter = Reporter(fields.get("reporter", {})).__dict__
        else:
            self.reporter = None
        if "customfield_10070" in fields:
            if fields["customfield_10070"] is not None:
                self.assay = fields["customfield_10070"][0].get("value", None)
            else:
                self.assay = None
        else:
            self.assay = None


class Jira:
    """
    Jira Class Wrapper for Jira API request
    """

    headers = {"Accept": "application/json"}

    http = requests.Session()
    retries = Retry(total=5, backoff_factor=10, method_whitelist=["POST"])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    def __init__(self, token, email, api_url, debug):
        self.auth = HTTPBasicAuth(email, token)
        self.api_url = api_url
        self.url = f"{api_url}/servicedeskapi/servicedesk"
        self.debug = debug

    def get_all_service_desk(self):
        """
        Get all service desk on Jira
        """
        url = self.url
        response = self.http.get(url, headers=self.headers, auth=self.auth)
        return response.json()

    def get_queues_in_service_desk(self, servicedesk_id):
        """
        Get all queues available in specified service desk on Jira
        """
        url = f"{self.url}/{servicedesk_id}/queue"
        response = self.http.get(url, headers=self.headers, auth=self.auth)
        return response.json()

    def get_all_issues(
        self, servicedesk_id: int, queue_id: int, trimmed: bool = False
    ) -> list:
        """
        Get all issues of a queue in specified service desk
        Inputs:
            servicedesk_id: service desk id
            queue_id: queue id (e.g. All Open or New Sequencing)
        """
        url = f"{self.url}/{servicedesk_id}/queue/{queue_id}/issue"
        response = self.http.get(url, headers=self.headers, auth=self.auth)

        count = 50
        issues = response.json()["values"]

        while response.json()["isLastPage"] is False:
            query_url = url + f"?start={count}"
            response = self.http.get(
                query_url, headers=self.headers, auth=self.auth
            )

            if not response.ok:
                raise Exception(f"Response returned error {response}")

            issues += response.json()["values"]
            count += 50

            if count > 5000:
                break

        if trimmed:
            result = []

            for issue in issues:
                result.append(Issue(issue).__dict__)
            return result
        return issues

    def get_issue(self, issue_id: Union[int, str], trimmed: bool = False):
        """
        Get details of specified issue
        If trimmed: return a pre-processed issue json()s
        Input:
            issue_id: issue id or key
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"
        response = self.http.get(url, headers=self.headers, auth=self.auth)
        if trimmed:
            return Issue(response.json()).__dict__
        return response.json()

    def search_issue(
        self, sequence_name: str, project_name: str = "EBH"
    ) -> dict:
        """
        Search issues based on sequence_name

        If cleaned: return a pre-processed issue json()

        Parameters:
            sequence_name: run name
            project_name: e.g. EBHD or EBH
        """

        url = f"{self.api_url}/api/3/search"
        query_cmd = f'project = {project_name} and summary ~ "{sequence_name}"'

        query = {"jql": query_cmd}
        response = self.http.get(
            url, headers=self.headers, params=query, auth=self.auth
        )

        return response.json()

    def get_assay(self, issue: dict):
        """
        Get assay options of an issue
        """
        if "customfield_10070" in issue["fields"]:
            return issue["fields"]["customfield_10070"][0].get("value", None)
        return None

    def get_issue_detail(self, run: str, server: bool) -> tuple:
        """
        Function to do an issue search and return its
        detail

        Returns:
            assay: e.g. TWE CEN MYE
            status: e.g. ALL SAMPLES RELEASED
            key: e.g. EBH-981 or None
        """

        if self.debug and not server:
            # debug = True and server = False
            desk = "EBHD"
        else:
            # debug = False / server = True
            desk = "EBH"

        jira_data = self.search_issue(run, project_name=desk)

        # if Jira return no result / error
        if (jira_data["total"] < 1) or ("errorMessages" in jira_data):
            assay = "No Jira ticket found"
            status = "No Jira ticket found"
            key = None

        elif jira_data["total"] > 1:
            # more than one issue found
            filtered_issues = []

            for result in jira_data["issues"]:
                # remove those that start with 'RE' (replies)
                # exclude those that're not sequencing issuetype
                sequencing_run = (
                    result["fields"].get("issuetype", {}).get("id", "")
                    == "10179"
                )
                reply = result["fields"]["summary"].startswith("RE")

                if sequencing_run and not reply:
                    filtered_issues.append(Issue(result))

            if len(filtered_issues) == 1:
                assay = filtered_issues[0].assay
                status = filtered_issues[0].status.name
                key = filtered_issues[0].key

            elif len(filtered_issues) == 0:
                assay = "No Jira ticket found after filtering"
                status = "No Jira ticket found after filtering"
                key = None

            else:
                assay = "More than 1 Jira ticket detected"
                status = "More than 1 Jira ticket detected"
                key = "Multiple"
        else:
            # only one Jira ticket found
            issue = Issue(jira_data["issues"][0])
            assay = issue.assay
            status = issue.status.name
            key = issue.key

        return assay, status, key

    def create_issue(
        self,
        summary: str,
        issue_id: int,
        project_id: int,
        reporter_id: str,
        priority_id: int,
        desc: str,
        assay: bool,
    ) -> dict:
        """
        Create a ticket issue
        Inputs:
            summary: issue title
            issue_id: id of issue type
            project_id: id of project
            reporter_id: id of reporter
            desc: issue description
            priority_id: id of priority (e.g. 3)
            assay: put an assay tag on issue
        """
        url = f"{self.api_url}/api/3/issue"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.debug:
            project_id = 10042

        if assay:
            # likely for debug purpose
            payload = json.dumps(
                {
                    "fields": {
                        "summary": summary,
                        "issuetype": {"id": str(issue_id)},
                        "project": {"id": str(project_id)},
                        "reporter": {"id": reporter_id},
                        "priority": {"id": str(priority_id)},
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"text": desc, "type": "text"}
                                    ],
                                }
                            ],
                        },
                        "customfield_10070": [{"value": "MYE"}],
                    }
                }
            )
        else:
            payload = json.dumps(
                {
                    "fields": {
                        "summary": summary,
                        "issuetype": {"id": str(issue_id)},
                        "project": {"id": str(project_id)},
                        "reporter": {"id": reporter_id},
                        "priority": {"id": str(priority_id)},
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"text": desc, "type": "text"}
                                    ],
                                }
                            ],
                        },
                    }
                }
            )

        response = self.http.post(
            url, data=payload, headers=headers, auth=self.auth
        )

        return response.json()

    def make_transition(self, issue_id, transition_id):
        """
        Make a transition for an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}/transitions"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = json.dumps({"transition": {"id": transition_id}})
        response = self.http.post(
            url, data=payload, headers=headers, auth=self.auth
        )
        sleep(1)  # add tiny delay to let Jira catch up on the back end
        if response.status_code == 204:
            return "Request successful"
        else:
            return response.text

    def delete_issue(self, issue_id):
        """
        Delete an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"
        response = requests.request("DELETE", url, auth=self.auth)

        if response.status_code == 204:
            return "Request successful"
        else:
            return response.text

    def get_available_transitions(self, issue_id):
        """
        Get all available transitions for an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}/transitions"

        response = self.http.get(url, headers=self.headers, auth=self.auth)

        return response.json()
