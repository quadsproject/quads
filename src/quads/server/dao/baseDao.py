from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from quads.server.models import Disk, Host, Interface, Memory, Processor, db

FILTERING_OPERATORS = {
    "==": "eq",
    "!=": "ne",
    ">": "gt",
    "<": "lt",
    ">=": "ge",
    "<=": "le",
    "like": "like",
    "ilike": "ilike",
    "in": "in",
}
OPERATORS = {
    "__ne": "!=",
    "__lt": "<",
    "__lte": "<=",
    "__gt": ">",
    "__gte": ">=",
    "__like": "like",
    "__ilike": "ilike",
    "__in": "in",
}
HAVING_OPERATORS = {
    "==": lambda column, value: column == value,
    "!=": lambda column, value: column != value,
    ">": lambda column, value: column > value,
    "<": lambda column, value: column < value,
    ">=": lambda column, value: column >= value,
    "<=": lambda column, value: column <= value,
}
MAP_HOST_META = {
    "interfaces": Interface,
    "disks": Disk,
    "memory": Memory,
    "processors": Processor,
}


class EntryNotFound(Exception):
    pass


class EntryExisting(Exception):
    pass


class InvalidArgument(Exception):
    pass


class SQLError(Exception):
    pass


class BaseDao:
    @staticmethod
    def safe_commit() -> bool:
        """
        Safely attempt to commit changes to MySQL.  Rollback in case of a failure.
        :return: True if the commit was successful, False if a rollback occurred.
        """
        try:
            for obj in db.session.new:
                current_app.logger.debug(f"New: {obj.__class__.__name__}: {obj}")
            for obj in db.session.dirty:
                current_app.logger.debug(f"Modified: {obj.__class__.__name__}: {obj}")
            for obj in db.session.deleted:
                current_app.logger.debug(f"Deleted: {obj.__class__.__name__}: {obj}")

            db.session.commit()
            return True
        except SQLAlchemyError as error:
            db.session.rollback()
            current_app.logger.error("SQL Commit Failed!  Rolling back...")
            current_app.logger.error(error.args)
            return False

    @classmethod
    def create_query_select(cls, model, filters=None, columns=None, group_by=None, order_by=None):
        """
        Create a query to select data from a model with filters and columns.
        :param model: The model to query.
        :param filters: A list of filter expressions.
        :param columns: A list of columns to select.
        :param group_by: A column to group by.
        :param order_by: A column to order by.
        :return: The query result.
        """
        group_by_column = None
        if group_by:
            group_by_column = cls.get_group_by_column(model=model, group_by=group_by)
            query_columns = [group_by_column, func.count(group_by_column)]
        else:
            query_columns = cls.create_query_columns(model=model, columns=columns)
        query = db.session.query(*query_columns)
        for expression in filters:
            try:
                column_name, op, value = expression
            except ValueError:  # pragma: no cover
                raise Exception("Invalid filter: %s" % expression)
            if op not in FILTERING_OPERATORS:
                raise Exception("Invalid filter operation: %s" % op)

            attrs = column_name.split(".")
            if len(attrs) > 1:
                column_name = attrs[0]
                parent_column = MAP_HOST_META[column_name]
                column = getattr(parent_column, attrs[1])
                query = query.filter(model.id == parent_column.host_id)
            else:
                column = getattr(model, column_name, None)
            if not column:
                raise Exception("Invalid filter column: %s" % column_name)

            try:
                attr = (
                    list(
                        filter(
                            lambda e: hasattr(column, e % FILTERING_OPERATORS[op]),
                            ["%s", "%s_", "__%s__"],
                        )
                    )[0]
                    % FILTERING_OPERATORS[op]
                )
            except IndexError:  # pragma: no cover
                raise Exception("Invalid filter operator: %s" % FILTERING_OPERATORS[op])

            if value == "null":
                value = None

            if column_name == "disks" and attrs[1] == "count":
                if group_by_column:
                    raise Exception("Group by column not allowed for disks count")

                query = query.outerjoin(parent_column, parent_column.host_id == model.id).group_by(model.id)
                if value:
                    operator_func = HAVING_OPERATORS.get(op)
                    if operator_func:
                        query = query.having(operator_func(func.sum(column), value))
                    else:
                        raise Exception("Invalid filter operator: %s" % op)
            else:
                query = query.filter(getattr(column, attr)(value))

        if group_by_column:
            query = query.group_by(group_by_column)

        if order_by is not None and not group_by:
            query = query.order_by(order_by)

        return query.all()

    @classmethod
    def create_query_columns(cls, model, columns):
        if not columns:
            return [model]

        cols = []
        for column in columns:
            _attr = getattr(model, column, None)
            if not _attr:
                raise Exception("Invalid column name %s" % column)
            cols.append(_attr)
        return cols

    @classmethod
    def get_group_by_column(cls, model, group_by):
        _attr = getattr(model, group_by)
        if not _attr:
            raise Exception("Invalid column name %s" % group_by)
        return _attr
