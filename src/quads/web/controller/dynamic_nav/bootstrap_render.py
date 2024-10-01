from quads.web.controller.dynamic_nav.markup_elements import SubMenuGroup


class HTMLElements:
    class nav:
        def __init__(self, element: any = '', *args, **kwargs):
            items = [f'{k}="{v}"' for k, v in kwargs.items()]
            self.elements = [f'<nav {" ".join(items)}>', str(element)]

        def add(self, element):
            self.elements.append(str(element))

        def __str__(self):
            return "".join(self.elements + ["</nav>"])

    class ul:

        def __init__(self, _class: str = '', *args, **kwargs):
            items = [f'{k}="{v}"' for k, v in kwargs.items()]
            self.element = [f'<ul class="{_class}" {" ".join(items)}>']

        def add(self, element):
            self.element.append(str(element))

        def __str__(self):
            return ''.join(self.element + ["</ul>"])

    class li:
        def __init__(self, element: any, _class: str = '', *args, **kwargs):
            element_string = ""
            if isinstance(element, tuple) or isinstance(element, list):
                for item in element:
                    element_string += str(item)
            else:
                element_string = str(element)
            self.element = f'<li class="{_class}">{str(element_string)}</li>'

        def __str__(self):
            return self.element

    class span:

        def __init__(self, _class: str = '', *args, **kwargs):
            items = [f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()]
            if args:
                self.element = f'<span class="{_class}" {" ".join(items)}>{"".join(args)}</span>'
            else:
                self.element = f'<span class="{_class}" {" ".join(items)}></span>'

        def __str__(self):
            return self.element

    class div:
        def __init__(self, element: any, groups: any = '', _class: str = '', *args, **kwargs):
            items = [f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()]
            self.element = f'<div class="{_class}" {" ".join(items)}>{str(element)}' \
                           f'{str(groups)}' \
                           f'</div>'

        def __str__(self):
            return self.element

    class a:
        def __init__(self, href: str, title: str, _class: str = '', *args, **kwargs):
            items = [f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()]
            self.element = f'<a href="{href}" class="{_class}" {" ".join(items)}>{title}</a>'

        def __str__(self):
            return self.element

    class button:
        def __init__(self, element: any = '', _class: str = '', *args, **kwargs):
            items = [f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()]
            self.element = f'<button class="{_class}" {" ".join(items)}>{str(element)}</button>'

        def __str__(self):
            return self.element


class BootStrap5Render:
    """
    A very basic Bootstrap 5 renderer.
    Renders a navigational structure using ``<nav>`` and ``<ul>`` tags that
    can be styled using modern CSS.
    """

    def __init__(self, **kwargs):
        """Constructor for ``SimpleRenderer``."""
        self.kwargs = kwargs
        self.elements = HTMLElements()

    def visit(self, node):
        """
        Visit a node.
        """
        if isinstance(node, type):
            mro = node.mro()
        else:
            mro = type(node).mro()
        for cls in mro:
            meth = getattr(self, 'visit_' + cls.__name__, None)
            if meth is None:
                continue
            return meth(node)

        raise NotImplementedError('No visitation method visit_{}'
                                  .format(node.__class__.__name__))

    def visit_Link(self, node):
        """Returns hrefs matching url."""
        return self.elements.a(title=node.text, href=node.get_url(), _class="nav-link")

    def visit_Navbar(self, node):
        """Returns navbar classes."""
        kwargs = self.kwargs.copy()

        add_class = []
        if "class" in self.kwargs:
            add_class = kwargs["class"].split(" ")

        kwargs["class"] = " ".join(add_class + ["navbar", "navbar-expand-lg"])
        icon = self.elements.span(_class="navbar-toggler-icon")

        button = self.elements.button(element=icon, _class="navbar-toggler btn",
                                      data_bs_toggle="collapse",
                                      data_bs_target="#navbarSupportedContent")
        cont = self.elements.nav(button, **kwargs)
        ul = self.elements.ul(id="navbarSupportedContent",
                              _class=" ".join(add_class + ["nav collapse navbar-collapse"]))

        for item in node.items:
            ul.add(self.elements.li(self.visit(item), _class="nav-item"))
        cont.add(ul)
        return cont

    def visit_View(self, node):
        """Returns hrefs."""
        class_values = "nav-link"
        if node.active:
            class_values = "nav-link active"
        return self.elements.a(
            href=node.get_url(),
            title=node.text,
            _class=class_values,
        )

    def visit_Subgroup(self, node):
        """Returns subgroup divs."""
        group = self.elements.ul(_class="dropdown-menu")
        title = self.elements.a(
            title=node.title,
            href="#",
            _class="nav-link dropdown-toggle",
            data_bs_toggle="dropdown"
        )

        for item in node.items:
            if isinstance(item, SubMenuGroup):
                group.add(self.elements.li(self.visit(item), _class="dropdown-item dropdown-submenu"))
            else:
                group.add(self.elements.li(self.visit(item), _class="dropdown-item"))

        return self.elements.div(title, group, _class="dropdown")

    def visit_SubMenuGroup(self, node):
        """Returns subMenuGroup divs."""
        group = self.elements.ul(_class="dropdown-menu")
        title = self.elements.a(
            title=node.title,
            href="#",
            _class="nav-link dropdown-toggle menu-title",
        )

        for item in node.items:
            if isinstance(item, SubMenuGroup):
                group.add(self.elements.li(self.visit(item), _class="dropdown-item dropdown-submenu"))
            else:
                group.add(self.elements.li(self.visit(item), _class="dropdown-item submenu-item"))

        return title, group
