# QUADS Self Scheduling

On QUADS 2.2.0 we introduced a new feature called `self-scheduling` which allows users to schedule their own hosts without the need of a QUADS admin to do it for them. This feature is available via the QUADS REST API and is disabled by default.

For more details on the API, please refer to our [Swagger Documentation](https://app.swaggerhub.com/apis-docs/RedHatScale/quads/3.0.0).

* [Self-Scheduling How-To](#self-scheduling-how-to)
  * [Via REST API](#via-rest-api)
    * [Register via REST](#register-via-rest)
    * [Login via REST](#login-via-rest)
    * [Get available hosts via REST](#get-available-hosts-via-rest)
    * [Create an assignment via REST](#create-an-assignment-via-rest)
    * [Schedule a host via REST](#schedule-a-host-via-rest)
    * [Wait for validation via REST](#wait-for-validation-via-rest)
    * [Terminate assignment via REST](#terminate-assignment-via-rest)
  * [Via python-quads-lib](#via-python-quads-lib)
    * [Register via Python](#register-via-python)
    * [Login via Python](#login-via-python)
    * [Get available hosts via Python](#get-available-hosts-via-python)
    * [Create an assignment via Python](#create-an-assignment-via-python)
    * [Schedule a host via Python](#schedule-a-host-via-python)
    * [Wait for validation via Python](#wait-for-validation-via-python)
    * [Terminate assignment via Python](#terminate-assignment-via-python)
  * [Via Ansible](#via-ansible)

# Self-Scheduling How-To

## Via REST API

* In this example we're using the following values

| Email           | Username  | Password   | QUADS Server      |
|-----------------|-----------|------------|-------------------|
| joe@example.com | joe       | make one up| quads.example.com |

### Register via REST

```bash
curl -s -k \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"email": "joe@example.com", "password": "a_password_here"}' \
  https://quads.example.com/api/v3/register
```

### Login via REST

```bash
export TOKEN=$(sed -e 's/^"//' -e 's/"$//' <<< $(curl -s -k -X POST \
    -u "joe@example.com:a_password_here" \
    -H "Content-Type: application/json" \
    https://quads.example.com/api/v3/login/ | awk -F\: '{print $2}' | awk -F\, '{print $1}'
  )
)
```

### Get available hosts via REST

```bash
curl -s https://quads.example.com/api/v3/available\?can_self_schedule\=true | jq
```
  > [!TIP]
  > Additional HW [filtering](https://github.com/redhat-performance/quads/blob/latest/docs/quads-host-metadata-search.md#example-hardware-filter-searches) is available via the `filter` parameter.

### Create an assignment via REST

> [!NOTE]
> The `owner` field is the username as it is on the email address but without the domain part.
>
> Passing no cloud will auto select the first available one.
>
> A JIRA ticket is created automatically if none is provided and if the service is enabled.
>
> There are other options as well like if your lab supports it like `"vlan": "620",` for an optional, routable VLAN.

```bash
curl -s -k \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Short description here", "owner": "joe", "qinq": 0, "wipe": "true"}' \
  http://quads.example.com/api/v3/assignments/self | jq
```

### Schedule a host via REST

> [!NOTE]
> Use the cloud name that was used in the assignment creation or returned in the assignment creation response.
>
> `"name": "cloud02"`
>
> Start and end dates are not required.
>
> Start date is now and end date is whatever is set in your `/opt/quads/conf/selfservice.yml` [configuration](https://github.com/redhat-performance/quads/blob/latest/conf/selfservice.yml#L6) for `ssm_default_lifetime`.

> [!NOTE]
> Replace `host01.example.com` with any desired free host from your previous available query

```bash
curl -s -k \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cloud":"cloud02", "hostname": "host1.example.com"}' http://quads.example.com/api/v3/schedules | jq
```

> [!TIP]
> To add more than one host to your assignment run the schedule command for as many other hosts as you need.
>
> This is managed by the `ssm_host_limit` setting in `/opt/quads/conf/selfservice.yml`

### Wait for validation via REST

> [!NOTE]
> The `assignment id` is the one returned in the assignment creation response e.g. `"assignment_id": 111,`
>
> You can poll this endpoint every so often until the assignment is validated.

```bash
curl -s http://quads.example.com/api/v3/assignments/assignment_id | jq | grep validated
```

### Terminate assignment via REST

```bash
curl -s -k \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  https://quads.example.com/api/v3/assignments/terminate/assignment_id | jq
```

## Via python-quads-lib

* Requires the [python-quads-lib](https://python-quads-lib.readthedocs.io/en/stable/readme.html#installation) library.

### Register via Python
```python
from quads_lib import QuadsApi
username = "joe@example.com"
password = "a_new_password"
base_url = "https://quads.example.com"
quads = QuadsApi(username, password, base_url)
quads.register()
```

### Login via Python
```python
from quads_lib import QuadsApi
quads = QuadsApi(username, password, base_url)
quads.login()
```

> [!NOTE]
> If using the [quads-lib](https://python-quads-lib.readthedocs.io/en/latest/usage.html) with the context manager, you don't need to call the login method and the logout method will be called automatically when the context manager exits.

### Get available hosts via Python
```python
from quads_lib import QuadsApi

filter = {"can_self_schedule": True}

with QuadsApi(username, password, base_url) as quads:
    hosts = quads.filter_available(filter)
```

### Create an assignment via Python
> [!NOTE]
> The `owner` field is the username minus the `@example.com` part of the email string, e.g. `joe`
>
```python
from quads_lib import QuadsApi

description = "Short description here"
owner = "user"
qinq = 0
wipe = True
payload = {
  "description": description, "owner": owner, "qinq": qinq, "wipe": wipe}

with QuadsApi(username, password, base_url) as quads:
    assignment = quads.create_assignment(payload)
```

### Schedule a host via Python
```python
from quads_lib import QuadsApi

payload = {"cloud":"cloud02", "hostname": "host1.example.com"}

with QuadsApi(username, password, base_url) as quads:
    quads.create_schedule(payload)
```

### Wait for validation via Python
```python
from quads_lib import QuadsApi

while True:
  with QuadsApi(username, password, base_url) as quads:
      assignment = quads.get_active_cloud_assignment("cloud02")
      if assignment.validated:
          break
      time.sleep(1)
```

### Terminate assignment via Python
```python
from quads_lib import QuadsApi

with QuadsApi(username, password, base_url) as quads:
    quads.terminate_assignment(assignment_id)
```

## Via Ansible

* You can use our QUADS self-scheduling [Ansible playbook here](https://github.com/quadsproject/ansible-quads-ssm)
* Refer to the usage documentation there.
