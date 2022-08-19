import requests
from requests.auth import HTTPBasicAuth


class Assignee(object):
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.active = data.get('active', None)
        self.name = data.get('displayName', None)
        self.timezone = data.get('timeZone', None)


class Reporter(object):
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.account_type = data.get('accountType', None)
        self.active = data.get('active', None)
        self. name = data.get('displayName', None)
        self.email = data.get('emailAddress', None)
        self.time = data.get('timeZone', None)


class Creator(object):
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.account_type = data.get('accountType', None)
        self.active = data.get('active', None)
        self.name = data.get('displayName', None)
        self.time = data.get('timeZone', None)


class Priority(object):
    def __init__(self, data):
        self.id = data.get('id', None)
        self.name = data.get('name', None)


class Project(object):
    def __init__(self, data):
        self.id = data.get('id', None)
        self.key = data.get('key', None)
        self.name = data.get('name', None)
        self.category = data.get('projectCategory', None)


class Status(object):
    def __init__(self, data):
        self.id = data.get('id', None)
        self.name = data.get('name', None)
        self.category = data.get('statusCategory', None)


class Issue(object):
    def __init__(self, data):
        self.id = data['id']
        self.key = data['key']

        fields = data['fields']
        self.created = fields.get('created', None)
        self.creator = Creator(fields.get('creator', {})).__dict__
        self.priority = Priority(fields.get('priority', {})).__dict__
        self.summary = fields.get('summary', None)
        self.updated = fields.get('updated', None)
        if 'assignee' in fields:
            if fields['assignee'] is not None:
                self.assignee = Assignee(fields.get('assignee', {})).__dict__
            else:
                self.assignee = None
        else:
            self.assignee = None
        if 'status' in fields:
            self.status = Status(fields.get('status', {})).__dict__
        else:
            self.status = None
        if 'project' in fields:
            self.project = Project(fields.get('project', {})).__dict__
        else:
            self.project = None
        if 'reporter' in fields:
            self.reporter = Reporter(
                fields.get('reporter', {})).__dict__
        else:
            self.reporter = None
        if 'customfield_10070' in fields:
            if fields['customfield_10070'] is not None:
                self.array = fields['customfield_10070'][0].get('value', None)
            else:
                self.array = None
        else:
            self.array = None


class Jira():
    """
    Jira Class for API request
    EBH is service desk number 4, All Open 14
    EBHD is service desk number 5, All Open 18
    """
    headers = {"Accept": "application/json"}
    api_url = 'https://cuhbioinformatics.atlassian.net/rest'
    service_url = f'{api_url}/servicedeskapi/servicedesk'

    def __init__(self, token, email):
        self.auth = HTTPBasicAuth(email, token)

    def get_all_service_desk(self):
        """
        Get all service desk on Jira
        """
        url = self.service_url
        response = requests.request(
            "GET",
            url,
            headers=self.headers,
            auth=self.auth)
        return response.json()

    def get_queues_in_service_desk(self, servicedesk_id):
        """
        Get all queues available in specified service desk on Jira
        """
        url = f"{self.service_url}/{servicedesk_id}/queue"
        response = requests.request(
            "GET",
            url,
            headers=self.headers,
            auth=self.auth)
        return response.json()

    def get_all_issues(
            self,
            servicedesk_id: int,
            queue_id: int,
            trimmed: bool = False):
        """
        Get all issues of a queue in specified service desk
        """
        url = f"{self.service_url}/{servicedesk_id}/queue/{queue_id}/issue"
        response = requests.request(
            "GET",
            url,
            headers=self.headers,
            auth=self.auth)

        if trimmed:
            result = []
            data = response.json()

            for issue in data['values']:
                result.append(Issue(issue).__dict__)

            return {
                'size': data['size'],
                'isLastPage': data['isLastPage'],
                'limit': data['limit'],
                'start': data['start'],
                'values': result
                }

        return response.json()

    def get_issue(
            self,
            issue_id: int,
            trimmed: bool = False):
        """
        Get details of specified issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"
        response = requests.request(
            "GET",
            url,
            headers=self.headers,
            auth=self.auth)
        if trimmed:
            return Issue(response.json())
        return response.json()

    def search_issue(
            self,
            sequence_name: str,
            arrays: list = [],
            project_name: str = 'EBH',
            status: list = [],
            trimmed: bool = False):
        """
        Search issues based on input text
        Inputs:
            arrays: limit search to certain arrays
            status: limit search to certain status
        """

        url = f"{self.api_url}/api/3/search"
        query_cmd = f'project={project_name} and summary ~ \"{sequence_name}\"'
        if status:
            status_options = ','.join('"{0}"'.format(w) for w in status)
            query_cmd += f' and status IN ({status_options})'

        query = {'jql': query_cmd}
        response = requests.request(
            "GET",
            url,
            headers=self.headers,
            params=query,
            auth=self.auth)
        res = response.json()
        if 'errorMessages' in res:
            return res
        elif len(res['issues']) == 0:
            return res

        if arrays:
            arrays = [a.lower() for a in arrays]
            if len(res['issues']) > 1:
                print('Multiple issue found.')
                output = []
                for issue in res['issues']:
                    array = self.get_array(issue)
                    if array.lower() in arrays:
                        output.append(Issue(issue))
                if output:
                    return output
                else:
                    print('no ticket fits array options')
                    return {'total': 0}
            else:
                issue = res['issues'][0]
                array = self.get_array(issue)
                if array.lower() in arrays:
                    if trimmed:
                        return {
                            'total': res['total'],
                            'maxResults': res['maxResults'],
                            'startAt': res['startAt'],
                            'issues': Issue(issue).__dict__
                        }
                    else:
                        return res
                else:
                    print('no ticket fits array options')
                    return {'total': 0}
        else:
            if trimmed:
                if len(res['issues']) > 1:
                    issues = []
                    for issue in res['issues']:
                        issues.append(Issue(issue).__dict__)

                    return {
                        'total': res['total'],
                        'maxResults': res['maxResults'],
                        'startAt': res['startAt'],
                        'issues': issues
                    }
                else:
                    issue = res['issues'][0]
                    return {
                        'total': res['total'],
                        'maxResults': res['maxResults'],
                        'startAt': res['startAt'],
                        'issues': Issue(issue).__dict__
                    }

            else:
                return res

    def get_array(
            self,
            issue: dict):
        """
        Get array options of an issue
        """
        if 'customfield_10070' in issue['fields']:
            return issue['fields']['customfield_10070'][0].get('value', None)
        return None

    def get_issue_detail(
            self,
            project: str):

        """
        Function to do an issue search and return its
        array options and status
        """

        jira_data = self.search_issue(
            project,
            project_name='EBH',
            trimmed=True)

        if jira_data['total'] < 1:
            array = 'No Jira ticket found'
            status = 'No Jira ticket found'
            key = None
        elif jira_data['total'] > 1:
            issues = jira_data['issues']

            the_issue = [
                issue for issue in issues if not issue['summary'].startswith(
                    'RE')]
            if len(the_issue) == 1:
                array = the_issue[0]['array']
                status = the_issue[0]['status']['name']
                key = the_issue[0]['key']
            else:
                array = 'More than 1 Jira ticket detected'
                status = 'More than 1 Jira ticket detected'
                key = None
        else:
            array = jira_data['issues']['array']
            status = jira_data['issues']['status']['name']
            key = jira_data['issues']['key']

        return array, status, key
