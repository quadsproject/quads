from quads.web.controller.dynamic_nav.bootstrap_render import BootStrap5Render


def register_renderer(app, iid, renderer, force=True):
    """
    Registers a renderer on the application.
    """
    renderers = app.extensions.setdefault("nav_renderers", {})

    if force:
        renderers[iid] = renderer
    else:
        renderers.setdefault(iid, renderer)


class DynamicNav:

    def __init__(self):
        self.elements = {}
        self._renderers = [("BootStrapRender5", BootStrap5Render)]

    def init_app(self, app):
        """
        Initialize an application.
        """
        if not hasattr(app, "extensions"):
            app.extensions = {}

        app.extensions["nav"] = self
        app.add_template_global(self.elements, "nav")

        for args in self._renderers:
            register_renderer(app, *args)

    def register_element(self, iid, elem):
        """
        Registers the given navigational element, making it available using the
        id ``iid``.
        """
        self.elements[iid] = elem
