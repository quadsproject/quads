from quads.quads_api import QuadsApi
from quads.server import models


class QuadsApiProxy:
    def __init__(self, config):
        self.api_wrapper = QuadsApi(
            username=config["quads_api_username"],
            password=config["quads_api_password"],
            base_url=config.API_URL,
        )

    def __enter__(self):
        self.api_wrapper.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.api_wrapper.logout()
        self.api_wrapper.session.close()

    def __getattr__(self, name):
        """
        Dynamically forward method calls to the underlying API wrapper
        and apply transformations based on metadata.
        """

        def wrapper(*args, **kwargs):
            method = getattr(self.api_wrapper, name)

            json_response = method(*args, **kwargs)
            if json_response is None:
                return None

            resource_type = getattr(method, "_returns", None)
            if resource_type is None:
                return json_response

            is_list = resource_type.startswith("list[")
            if is_list:
                resource_type = resource_type[5:-1]  # Remove "list[" and "]"

            resource = getattr(models, resource_type)
            if is_list:
                return [resource.from_dict(resource, item) for item in json_response]
            else:
                return resource.from_dict(resource, json_response)

        return wrapper
