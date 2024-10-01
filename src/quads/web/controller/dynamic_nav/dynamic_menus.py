import os

from quads.web.controller.dynamic_nav.markup_elements import SubMenuGroup, Link, Subgroup, View


class DynamicMenus:

    def __init__(self, web_dir_path: str, exclude_dir_path: str):
        self.web_dir_path = web_dir_path
        self.exclude_dir_path = exclude_dir_path

    def sort_list(self, menu_list: list, sort_keyword: str = None, sort_dir: bool = False) -> list:
        """
        This method sorts the links
        """
        numbered_links = []
        unnumbered_links = []
        for link in menu_list:
            ln = link[sort_keyword] if not sort_dir else link
            try:
                int(ln.split("_")[0])
                numbered_links.append(link)
            except ValueError:
                unnumbered_links.append(link)

        sorted_numbered_links = sorted(numbered_links, key=lambda x: x if sort_dir else x[sort_keyword])
        sorted_unnumbered_links = sorted(unnumbered_links, key=lambda x: x if sort_dir else x[sort_keyword])

        stripped_numbered_items = []
        stripped_unnumbered_items = []

        for item in sorted_numbered_links:
            if sort_dir:
                sm = "_".join(item.split("_")[1:])
                stripped_numbered_items.append({"dir": item, "name": sm})
            else:
                item[sort_keyword] = " ".join(item[sort_keyword].split()[1:])
                stripped_numbered_items.append(item)

        if sort_dir:
            for sm in sorted_unnumbered_links:
                sm_dir = sm
                stripped_unnumbered_items.append({"dir": sm_dir, "name": sm})
        else:
            stripped_unnumbered_items = sorted_unnumbered_links

        return stripped_numbered_items + stripped_unnumbered_items

    def get_files(self, file_path: str, exclude_dirs: str = None, parent_dir: str = None):
        """
        This method return the generated links
        """
        if not exclude_dirs:
            exclude_dirs = self.exclude_dir_path
        links = []
        files = [file.name for file in os.scandir(file_path)
                 if file.is_file() and file.name not in exclude_dirs]
        for file in files:
            link = {}
            if file.endswith(".html"):
                url_args = {"page": f"{file.replace('.html', '')}",
                            "endpoint": "content.dynamic_content"}
                if parent_dir:
                    url_args.update({"directory": parent_dir,
                                     "endpoint": "content.dynamic_content_sub"})
                link = url_args
                link["text"] = file.replace(".html", "").replace("_", " ")
                links.append(link)
            else:
                with open(os.path.join(file_path, file)) as f:
                    link["dest"] = f.readline().strip()
                link["text"] = file.replace("_", " ")
                links.append(link)

        return self.sort_list(menu_list=links, sort_keyword='text')

    def get_submenus(self, file_path: str, exclude_dirs: str = None):
        """
        This method return directories, it used as menu title
        """
        if not exclude_dirs:
            exclude_dirs = self.exclude_dir_path
        submenus = [d.name for d in os.scandir(file_path) if d.is_dir() and d.name not in exclude_dirs]
        sorted_submenus = self.sort_list(menu_list=submenus, sort_dir=True)
        return sorted_submenus

    def get_submenu_list(self, submenus: list, file_path: str, exclude_dirs: str = None):
        if not exclude_dirs:
            exclude_dirs = self.exclude_dir_path
        menus = {}
        for sub in submenus:
            sub_path = os.path.join(file_path, sub["dir"])
            sub_dirs = self.get_submenus(file_path=sub_path, exclude_dirs=exclude_dirs)
            if sub_dirs:
                sub_links = self.get_submenu_list(submenus=sub_dirs, file_path=sub_path, exclude_dirs=exclude_dirs)
                menus.setdefault(sub["name"], []).append(sub_links)
            sub_links = self.get_files(sub_path, exclude_dirs, parent_dir=sub["dir"])
            menus.setdefault(sub["name"], []).extend(sub_links)
        return menus

    def generate_views_list(self, menu_list: list):
        """
        This method returns the views list
        """
        views_list = []
        for menu in menu_list:
            for key, values in menu.items():
                if isinstance(values, list):
                    sub_views = self.generate_views_list(values)
                    views_list.append(SubMenuGroup(key, *sub_views))
                else:
                    views_list.append(Link(**menu) if 'dest' in menu else View(**menu))
                    break
        return views_list

    def generate_html_elements(self, dynamic_navbar_menus: dict):
        dynamic_navbar_elements = []
        for title, menu_list in dynamic_navbar_menus.items():
            dynamic_navbar_elements.append(
                Subgroup(title, *self.generate_views_list(menu_list))
            )
        return dynamic_navbar_elements

    def get_dynamic_navbar_menus(self):
        """
        This method return the dynamic navigation menu
        """
        menus = self.get_submenus(file_path=self.web_dir_path)

        dynamic_navbar_menus = self.get_submenu_list(submenus=menus, file_path=self.web_dir_path)
        files = self.get_files(file_path=self.web_dir_path)
        subgroup_elements = self.generate_html_elements(dynamic_navbar_menus)
        subgroup_elements += self.generate_views_list(files)
        return subgroup_elements
