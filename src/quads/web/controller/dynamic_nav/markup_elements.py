from importlib import import_module

from flask import current_app, url_for, request
from markupsafe import Markup


def get_renderer(app, iid):
    """
    Retrieve a renderer.
    """
    renderer = app.extensions.get("nav_renderers", {})[iid]
    if isinstance(renderer, tuple):
        mod_name, cls_name = renderer
        mod = import_module(mod_name)

        cls_name = mod
        for name in cls_name.split("."):
            cls_name = getattr(cls_name, name)

        return cls_name

    return renderer


class NavigationItem(object):
    """
    Base for all items in a Navigation.
    Every item inside a navigational view should derive from this class.
    """
    active = False

    def render(self, renderer=None, **kwargs):
        """
        Render the navigational item using a renderer.
        """
        return Markup(get_renderer(current_app, renderer)(**kwargs).visit(self))


class Link(NavigationItem):
    """An item that contains a link to a destination and a title."""

    def __init__(self, text, dest):
        self.text = text
        self.dest = dest

    def get_url(self):
        """Returns the URL to the destination."""
        return self.dest


class View(NavigationItem):
    """
    This
    """
    ignore_query = True

    def __init__(self, text, endpoint, **kwargs):
        """Constructor for View class."""
        self.text = text
        self.endpoint = endpoint
        self.url_for_kwargs = kwargs

    def get_url(self):
        """
        Return url for this item.
        """
        return url_for(self.endpoint, **self.url_for_kwargs)

    @property
    def active(self):
        """Return True it view is active."""
        if request.endpoint != self.endpoint:
            return False

        _, url = request.url_rule.build(
            self.url_for_kwargs,
            append_unknown=not self.ignore_query,
        )
        if self.ignore_query:
            return url == request.path
        return url == request.full_path


class Subgroup(NavigationItem):
    """
    Usually used to express a submenu.
    """
    def __init__(self, title, *items):
        self.title = title
        self.items = list(items)


class SubMenuGroup(Subgroup):
    """
    Usually used to express a nested - submenu.
    """


class Navbar(Subgroup):
    """Top level navbar."""
